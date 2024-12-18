import os
from typing import Set, List


class ProjectTreeGenerator:
    def __init__(self):
        # Default exclusion sets
        self.exclude_dirs: Set[str] = {
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".git",
            ".pytest_cache",
            "migrations",
            ".idea",
            ".vs",
            ".vscode",
        }

        self.exclude_files: Set[str] = {
            ".pyc",
            ".env",
            ".gitignore",
            ".DS_Store",
            ".coverage",
            ".pytest_cache",
            "__init__.py",
        }

        # Icons for better visualization
        self.icons = {
            "folder": "📁",
            "file": "📄",
            "python": "🐍",
            "json": "📋",
            "md": "📝",
            "txt": "📝",
            "csv": "📊",
            "data": "💾",
        }

    def get_file_icon(self, filename: str) -> str:
        """Return appropriate icon based on file extension"""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        return self.icons.get(ext, self.icons["file"])

    def should_exclude(self, name: str, is_dir: bool = False) -> bool:
        """Check if a file or directory should be excluded"""
        if is_dir:
            return name in self.exclude_dirs
        return name in self.exclude_files or any(name.endswith(ext) for ext in self.exclude_files)

    def generate_tree(self, startpath: str) -> List[str]:
        """Generate project tree structure"""
        tree_lines = []
        tree_lines.append(f"\nProject Tree for {startpath}")
        tree_lines.append("=" * 50)

        for root, dirs, files in os.walk(startpath):
            # Skip excluded directories
            dirs[:] = sorted([d for d in dirs if not self.should_exclude(d, True)])

            # Calculate current level for indentation
            level = root.replace(startpath, "").count(os.sep)
            indent = "  " * level

            # Add directory name
            basename = os.path.basename(root)
            if basename:  # Skip for root directory
                tree_lines.append(f"{indent}{self.icons['folder']} {basename}/")

            # Add files
            subindent = "  " * (level + 1)
            for f in sorted(files):
                if not self.should_exclude(f):
                    icon = self.get_file_icon(f)
                    tree_lines.append(f"{subindent}{icon} {f}")

        return tree_lines

    def save_tree(self, startpath: str, output_file: str = "project_structure.txt"):
        """Generate and save tree structure to file"""
        tree_lines = self.generate_tree(startpath)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(tree_lines))

        return tree_lines


def main():
    generator = ProjectTreeGenerator()
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Generate and print tree
    tree_lines = generator.generate_tree(current_dir)
    print("\n".join(tree_lines))

    # Optionally save to file
    generator.save_tree(current_dir)
    print("\nTree structure has been saved to 'project_structure.txt'")


if __name__ == "__main__":
    main()
