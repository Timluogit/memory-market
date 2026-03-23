"""Cross-Encoder 重排效果评估脚本

用于评估重排对搜索相关性的提升效果：
- MRR (Mean Reciprocal Rank)
- NDCG (Normalized Discounted Cumulative Gain)
- CTR (Click-Through Rate) - 模拟
- 零结果率对比
- 性能指标（延迟、吞吐量）
"""
import asyncio
import time
import json
import argparse
from typing import List, Dict, Tuple
from pathlib import Path
from datetime import datetime
import statistics

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_, or_

from app.models.tables import Memory, Agent, Purchase
from app.services.reranking_service import get_reranking_service
from app.core.config import settings
from app.search.hybrid_search import get_hybrid_engine


# 数据库连接
DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class RerankingEvaluator:
    """重排评估器"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-large",
        top_k: int = 20,
        threshold: float = 0.5,
        output_dir: str = "./evaluation_results"
    ):
        """初始化评估器

        Args:
            model_name: Cross-Encoder 模型名称
            top_k: Top-K 数量
            threshold: 相关性阈值
            output_dir: 结果输出目录
        """
        self.model_name = model_name
        self.top_k = top_k
        self.threshold = threshold
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 获取服务
        self.rerank_service = get_reranking_service(
            model_name=model_name,
            top_k=top_k,
            threshold=threshold
        )
        self.hybrid_engine = get_hybrid_engine()

    async def create_test_dataset(
        self,
        num_queries: int = 50,
        num_memories: int = 1000
    ) -> Tuple[List[Dict], List[Dict]]:
        """创建测试数据集

        Args:
            num_queries: 查询数量
            num_memories: 记忆数量

        Returns:
            (queries, memories) 元组
        """
        async with async_session() as db:
            # 获取随机记忆
            result = await db.execute(
                select(Memory)
                .where(Memory.is_active == True)
                .where(Memory.content.isnot(None))
                .limit(num_memories)
            )
            memories = result.scalars().all()

            # 生成测试查询
            queries = []
            for memory in memories[:num_queries]:
                queries.append({
                    'query': memory.title or memory.summary or "test",
                    'memory_id': memory.memory_id,
                    'category': memory.category,
                    'text': (memory.content or '')[:500]  # 取前500字符
                })

            return queries, [
                {
                    'memory_id': m.memory_id,
                    'title': m.title,
                    'summary': m.summary,
                    'content': str(m.content)[:500] if m.content else '',
                    'category': m.category,
                    'avg_score': m.avg_score
                }
                for m in memories
            ]

    async def evaluate_mrr_ndcg(
        self,
        queries: List[Dict],
        memories: List[Dict]
    ) -> Dict[str, float]:
        """评估 MRR 和 NDCG

        Args:
            queries: 测试查询列表
            memories: 记忆列表

        Returns:
            评估指标字典
        """
        mrr_scores = []
        ndcg_5_scores = []
        ndcg_10_scores = []

        print(f"\n{'='*60}")
        print(f"评估 {len(queries)} 个查询的 MRR/NDCG...")
        print(f"{'='*60}")

        for i, query in enumerate(queries, 1):
            # 准备候选结果
            candidates = memories.copy()

            # 执行重排
            start_time = time.time()
            reranked = await self.rerank_service.rerank(
                query['query'],
                candidates,
                top_k=self.top_k,
                threshold=self.threshold,
                use_cache=False  # 评估时不使用缓存
            )
            latency = (time.time() - start_time) * 1000  # 毫秒

            # 计算 MRR（正确答案在第一个位置）
            ground_truth = [query['memory_id']]
            reranked_ids = [r['memory_id'] for r in reranked]

            mrr = self.rerank_service._calculate_mrr(reranked_ids, ground_truth)
            mrr_scores.append(mrr)

            # 计算 NDCG
            ndcg_5 = self.rerank_service._calculate_ndcg(reranked_ids, ground_truth, k=5)
            ndcg_10 = self.rerank_service._calculate_ndcg(reranked_ids, ground_truth, k=10)
            ndcg_5_scores.append(ndcg_5)
            ndcg_10_scores.append(ndcg_10)

            if i % 10 == 0 or i == len(queries):
                print(f"  进度: {i}/{len(queries)} | MRR: {mrr:.4f} | NDCG@5: {ndcg_5:.4f} | 延迟: {latency:.1f}ms")

        # 计算平均指标
        avg_mrr = statistics.mean(mrr_scores)
        avg_ndcg_5 = statistics.mean(ndcg_5_scores)
        avg_ndcg_10 = statistics.mean(ndcg_10_scores)

        return {
            'mrr': avg_mrr,
            'ndcg@5': avg_ndcg_5,
            'ndcg@10': avg_ndcg_10,
            'num_queries': len(queries)
        }

    async def evaluate_performance(
        self,
        queries: List[Dict],
        memories: List[Dict],
        num_runs: int = 10
    ) -> Dict[str, float]:
        """评估性能指标

        Args:
            queries: 测试查询列表
            memories: 记忆列表
            num_runs: 运行次数

        Returns:
            性能指标字典
        """
        latencies = []
        throughputs = []

        print(f"\n{'='*60}")
        print(f"性能评估 ({num_runs} 次运行)...")
        print(f"{'='*60}")

        for run in range(1, num_runs + 1):
            start_time = time.time()
            processed = 0

            for query in queries:
                await self.rerank_service.rerank(
                    query['query'],
                    memories[:100],  # 限制候选数量以加速评估
                    top_k=self.top_k,
                    threshold=self.threshold,
                    use_cache=False
                )
                processed += 1

            elapsed = time.time() - start_time
            avg_latency = (elapsed / len(queries)) * 1000  # 平均延迟（毫秒）
            throughput = len(queries) / elapsed  # QPS

            latencies.append(avg_latency)
            throughputs.append(throughput)

            print(f"  运行 {run}/{num_runs} | 延迟: {avg_latency:.1f}ms | 吞吐量: {throughput:.1f} QPS")

        return {
            'avg_latency_ms': statistics.mean(latencies),
            'p50_latency_ms': statistics.median(latencies),
            'p95_latency_ms': sorted(latencies)[int(0.95 * len(latencies))],
            'p99_latency_ms': sorted(latencies)[int(0.99 * len(latencies))] if len(latencies) > 100 else max(latencies),
            'avg_throughput_qps': statistics.mean(throughputs)
        }

    async def evaluate_zero_result_rate(
        self,
        queries: List[Dict],
        memories: List[Dict]
    ) -> Dict[str, float]:
        """评估零结果率

        Args:
            queries: 测试查询列表
            memories: 记忆列表

        Returns:
            零结果率指标
        """
        zero_count = 0

        for query in queries:
            reranked = await self.rerank_service.rerank(
                query['query'],
                memories,
                top_k=self.top_k,
                threshold=self.threshold,
                use_cache=False
            )

            if not reranked:
                zero_count += 1

        zero_rate = zero_count / len(queries)

        return {
            'zero_result_rate': zero_rate,
            'zero_count': zero_count,
            'total_queries': len(queries)
        }

    async def evaluate_with_vs_without_rerank(
        self,
        queries: List[Dict],
        memories: List[Dict]
    ) -> Dict:
        """对比有/无重排的效果

        Args:
            queries: 测试查询列表
            memories: 记忆列表

        Returns:
            对比结果
        """
        print(f"\n{'='*60}")
        print(f"对比评估: 有重排 vs 无重排...")
        print(f"{'='*60}")

        # 有重排
        with_rerank_mrr = []
        without_rerank_mrr = []

        for i, query in enumerate(queries, 1):
            # 无重排：使用原始分数排序
            candidates = memories[:self.top_k]  # 取前 top_k
            without_rerank_ids = [c['memory_id'] for c in candidates]
            mrr_without = self.rerank_service._calculate_mrr(without_rerank_ids, [query['memory_id']])
            without_rerank_mrr.append(mrr_without)

            # 有重排
            reranked = await self.rerank_service.rerank(
                query['query'],
                memories,
                top_k=self.top_k,
                threshold=0.0,  # 不过滤
                use_cache=False
            )
            with_rerank_ids = [r['memory_id'] for r in reranked]
            mrr_with = self.rerank_service._calculate_mrr(with_rerank_ids, [query['memory_id']])
            with_rerank_mrr.append(mrr_with)

            if i % 10 == 0 or i == len(queries):
                print(f"  进度: {i}/{len(queries)} | 有重排MRR: {mrr_with:.4f} | 无重排MRR: {mrr_without:.4f}")

        return {
            'with_rerank_avg_mrr': statistics.mean(with_rerank_mrr),
            'without_rerank_avg_mrr': statistics.mean(without_rerank_mrr),
            'mrr_improvement': statistics.mean(with_rerank_mrr) - statistics.mean(without_rerank_mrr),
            'mrr_improvement_percent': ((statistics.mean(with_rerank_mrr) - statistics.mean(without_rerank_mrr)) / statistics.mean(without_rerank_mrr) * 100) if statistics.mean(without_rerank_mrr) > 0 else 0
        }

    async def run_full_evaluation(self, num_queries: int = 50, num_memories: int = 1000) -> Dict:
        """运行完整评估

        Args:
            num_queries: 查询数量
            num_memories: 记忆数量

        Returns:
            完整评估结果
        """
        print(f"\n{'#'*60}")
        print(f"# Cross-Encoder 重排效果评估")
        print(f"# 模型: {self.model_name}")
        print(f"# Top-K: {self.top_k}")
        print(f"# 阈值: {self.threshold}")
        print(f"{'#'*60}")

        # 创建测试数据集
        print(f"\n创建测试数据集...")
        queries, memories = await self.create_test_dataset(num_queries, num_memories)
        print(f"  查询数量: {len(queries)}")
        print(f"  记忆数量: {len(memories)}")

        # 运行各项评估
        results = {}

        # 1. MRR/NDCG 评估
        mrr_ndcg_results = await self.evaluate_mrr_ndcg(queries, memories)
        results.update(mrr_ndcg_results)

        # 2. 性能评估
        performance_results = await self.evaluate_performance(queries, memories, num_runs=5)
        results.update(performance_results)

        # 3. 零结果率评估
        zero_rate_results = await self.evaluate_zero_result_rate(queries, memories)
        results.update(zero_rate_results)

        # 4. 对比评估
        comparison_results = await self.evaluate_with_vs_without_rerank(queries, memories)
        results.update(comparison_results)

        # 添加元数据
        results.update({
            'model_name': self.model_name,
            'top_k': self.top_k,
            'threshold': self.threshold,
            'evaluation_time': datetime.now().isoformat()
        })

        # 保存结果
        self.save_results(results)

        # 打印摘要
        self.print_summary(results)

        return results

    def save_results(self, results: Dict):
        """保存评估结果到文件

        Args:
            results: 评估结果字典
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rerank_evaluation_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 评估结果已保存: {filepath}")

    def print_summary(self, results: Dict):
        """打印评估摘要

        Args:
            results: 评估结果字典
        """
        print(f"\n{'='*60}")
        print(f"评估摘要")
        print(f"{'='*60}")

        print(f"\n📊 相关性指标:")
        print(f"  MRR:                      {results['mrr']:.4f}")
        print(f"  NDCG@5:                   {results['ndcg@5']:.4f}")
        print(f"  NDCG@10:                  {results['ndcg@10']:.4f}")

        print(f"\n⚡ 性能指标:")
        print(f"  平均延迟:                 {results['avg_latency_ms']:.1f}ms")
        print(f"  P50 延迟:                 {results['p50_latency_ms']:.1f}ms")
        print(f"  P95 延迟:                 {results['p95_latency_ms']:.1f}ms")
        print(f"  平均吞吐量:               {results['avg_throughput_qps']:.1f} QPS")

        print(f"\n📈 效果提升:")
        print(f"  有重排 MRR:               {results['with_rerank_avg_mrr']:.4f}")
        print(f"  无重排 MRR:               {results['without_rerank_avg_mrr']:.4f}")
        print(f"  MRR 提升:                 {results['mrr_improvement']:.4f} ({results['mrr_improvement_percent']:.1f}%)")

        print(f"\n🔍 零结果率:")
        print(f"  零结果率:                 {results['zero_result_rate']:.2%} ({results['zero_count']}/{results['total_queries']})")

        print(f"\n✅ 目标达成情况:")
        print(f"  相关性提升 (+5-10%):      {'✓ 达成' if results['mrr_improvement_percent'] >= 5 else '✗ 未达成'}")
        print(f"  重排延迟 (<100ms):        {'✓ 达成' if results['p50_latency_ms'] < 100 else '✗ 未达成'}")
        print(f"  端到端延迟 (<200ms):      {'✓ 达成' if results['avg_latency_ms'] < 200 else '✗ 未达成'}")
        print(f"  吞吐量 (>50 QPS):         {'✓ 达成' if results['avg_throughput_qps'] > 50 else '✗ 未达成'}")

        print(f"\n{'='*60}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Cross-Encoder 重排效果评估")
    parser.add_argument('--model', type=str, default='BAAI/bge-reranker-large', help='模型名称')
    parser.add_argument('--top-k', type=int, default=20, help='Top-K 数量')
    parser.add_argument('--threshold', type=float, default=0.5, help='相关性阈值')
    parser.add_argument('--queries', type=int, default=50, help='测试查询数量')
    parser.add_argument('--memories', type=int, default=1000, help='测试记忆数量')
    parser.add_argument('--output', type=str, default='./evaluation_results', help='结果输出目录')

    args = parser.parse_args()

    # 创建评估器
    evaluator = RerankingEvaluator(
        model_name=args.model,
        top_k=args.top_k,
        threshold=args.threshold,
        output_dir=args.output
    )

    # 运行完整评估
    try:
        results = await evaluator.run_full_evaluation(
            num_queries=args.queries,
            num_memories=args.memories
        )
        print(f"\n✓ 评估完成！")
    except Exception as e:
        print(f"\n✗ 评估失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
