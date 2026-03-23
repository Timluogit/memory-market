"""外部数据源适配器 - 延迟导入"""

__all__ = [
    "GoogleDriveAdapter",
    "GmailAdapter",
    "NotionAdapter",
    "OneDriveAdapter",
    "GitHubAdapter",
    "LocalFolderAdapter",
]


def __getattr__(name):
    if name == "GoogleDriveAdapter":
        from .google_drive_adapter import GoogleDriveAdapter
        return GoogleDriveAdapter
    elif name == "GmailAdapter":
        from .gmail_adapter import GmailAdapter
        return GmailAdapter
    elif name == "NotionAdapter":
        from .notion_adapter import NotionAdapter
        return NotionAdapter
    elif name == "OneDriveAdapter":
        from .onedrive_adapter import OneDriveAdapter
        return OneDriveAdapter
    elif name == "GitHubAdapter":
        from .github_adapter import GitHubAdapter
        return GitHubAdapter
    elif name == "LocalFolderAdapter":
        from .local_folder_adapter import LocalFolderAdapter
        return LocalFolderAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
