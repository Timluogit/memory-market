# Market Capture

## Description
Automatically capture and structure your experiences as you work. The capture system monitors your problem-solving process and creates well-structured memories ready for upload to the marketplace.

## Trigger
- `/market capture start`
- `/market capture stop`
- `/market capture status`
- "start capturing experiences"
- "record this session"
- "capture my work"

## Usage

### Start a Capture Session
```
/market capture start --session "debugging API issue"
```

### Stop and Review
```
/market capture stop
```

### Check Status
```
/market capture status
```

### Auto-Capture Mode
```
/market capture start --auto
```
Automatically detects when you're solving problems and captures context.

## Capture Options

- `--session <name>`: Name for the capture session
- `--auto`: Enable automatic problem detection
- `--category <name>`: Pre-set category for captured memories
- `--tags <tags>`: Default tags for this session
- `--output <file>`: Save captured memory to file
- `--upload`: Automatically upload after capture

## What Gets Captured

The system captures:
- **Problem Context**: What you were trying to solve
- **Approach**: Steps you took
- **Challenges**: Obstacles encountered
- **Solutions**: What worked and what didn't
- **Code Snippets**: Relevant code examples
- **Lessons Learned**: Key takeaways
- **Related Errors**: Error messages and fixes

## Examples

### Capture a Debugging Session
```
/market capture start --session "fixing race condition"
[... you work on debugging the issue ...]
/market capture stop --upload
```

### Capture with Manual Annotation
```
/market capture start --session "API integration"
# During work, add notes:
/market capture note "Discovered that the API requires authentication header"
/market capture note "Rate limit is 100 requests/minute"
/market capture stop --category integration --tags "api,rest"
```

### Auto-Capture During Development
```
/market capture start --auto --category programming
# System automatically detects:
# - Bug fixes
# - Feature implementations
# - Refactoring work
# - Performance optimizations
/market capture stop
```

### Capture to File First
```
/market capture start --output ./captured-memory.md
[... work ...]
/market capture stop
# Review and edit the captured memory
/market upload --file ./captured-memory.md
```

## Capture Commands

### During an Active Session
- `/market capture note "<text>"`: Add a manual note
- `/market capture code`: Mark current code as relevant
- `/market capture error`: Record an error encountered
- `/market capture solution`: Mark a successful solution
- `/market capture pause`: Pause temporary (resume with `/market capture resume`)

## Best Practices

1. **Start Early**: Begin capture when you start a task
2. **Add Context**: Use capture notes to document your thought process
3. **Mark Key Moments**: Use commands to mark errors and solutions
4. **Review Before Upload**: Always review captured content before uploading
5. **Organize**: Use sessions and categories for organization

## Output Format

Captured memories are structured with:
```markdown
# Title: Auto-generated from session

## Problem
[What you were trying to solve]

## Approach
[Steps you took]

## Challenges
[Obstacles encountered]

## Solution
[What worked]

## Lessons Learned
[Key takeaways]

## Code Examples
[Relevant snippets]

## Metadata
- Session: [session name]
- Duration: [time]
- Category: [category]
- Tags: [tags]
```

## Integration with Workflow

Capture integrates seamlessly with your development workflow:
- Works alongside git commits
- Captures context from error messages
- Records successful debugging patterns
- Documents architectural decisions
- Preserves hard-earned knowledge

## After Capture

1. **Review**: Check the captured memory for accuracy
2. **Edit**: Add missing context or clarify points
3. **Enhance**: Add code examples or references
4. **Upload**: Share with the community (or keep private)

## Tips

- Use descriptive session names for easy organization
- Add capture notes for non-obvious decisions
- Review captured content before uploading
- Remove sensitive information (API keys, passwords)
- Add relevant tags for discoverability

## Related Skills
- `/market upload`: Upload captured memories
- `/market search`: Find similar memories before starting work
