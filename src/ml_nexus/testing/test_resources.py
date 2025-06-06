from ml_nexus.project_structure import ProjectDef, ProjectDir

default_ignore_set = [
    ".git",
    ".venv",
    ".idea",
    "__pycache__",
    ".pyc",
    ".idea",
    ".log",
    "src/wandb",
    "*.pth",
    "*.pkl",
    "*.tar.gz",
    "venv",
    "*.mdb",
]
test_project = ProjectDef(
    [
        ProjectDir(
            "ml-nexus",
            kind="rye",
            excludes=default_ignore_set,
        )
    ]
)
