import os

def generate_tree(startpath):
    exclude_dirs = {'venv', 'node_modules', '__pycache__', '.git', '.pytest_cache', 'migrations'}
    exclude_files = {'.pyc', '.env', '.gitignore', '.DS_Store'}
    
    print(f"\nProject Tree for {startpath}")
    print("=" * 50)
    
    for root, dirs, files in os.walk(startpath):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = '  ' * level
        print(f"{indent}📁 {os.path.basename(root)}/")
        
        subindent = '  ' * (level + 1)
        for f in sorted(files):
            if not any(f.endswith(ext) for ext in exclude_files):
                print(f"{subindent}📄 {f}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    generate_tree(current_dir)