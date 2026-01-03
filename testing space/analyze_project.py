"""Generate a complete project class and method inventory"""
import ast
import os
from pathlib import Path

def analyze_python_file(file_path):
    """Extract classes and methods from a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        classes = {}
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)
                classes[node.name] = methods
            elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                # Top-level functions only
                functions.append(node.name)
                
        return classes, functions
    except Exception as e:
        return {}, []

def scan_project():
    """Scan entire project structure"""
    project_map = {}
    
    # Define the structure you want to analyze
    scan_dirs = ['app/routers', 'app/services', 'app/utils', 'app/models.py', 'app/main.py']
    
    for scan_path in scan_dirs:
        if os.path.isfile(scan_path):
            # Single file
            classes, functions = analyze_python_file(scan_path)
            if classes or functions:
                project_map[scan_path] = {'classes': classes, 'functions': functions}
        elif os.path.isdir(scan_path):
            # Directory
            for file_path in Path(scan_path).glob('*.py'):
                if file_path.name != '__init__.py':
                    classes, functions = analyze_python_file(file_path)
                    if classes or functions:
                        project_map[str(file_path)] = {'classes': classes, 'functions': functions}
    
    return project_map

def generate_report():
    """Generate formatted project structure report"""
    project_map = scan_project()
    
    print("=" * 80)
    print("RECONOMED PROJECT STRUCTURE ANALYSIS")
    print("=" * 80)
    
    for file_path, content in sorted(project_map.items()):
        print(f"\n📁 {file_path}")
        print("-" * len(file_path))
        
        # Classes
        if content['classes']:
            for class_name, methods in content['classes'].items():
                print(f"  🔷 Class: {class_name}")
                for method in sorted(methods):
                    print(f"     • {method}()")
        
        # Top-level functions
        if content['functions']:
            print(f"  🔧 Functions:")
            for func in sorted(content['functions']):
                print(f"     • {func}()")
    
    print("\n" + "=" * 80)
    
    # Summary
    total_classes = sum(len(content['classes']) for content in project_map.values())
    total_methods = sum(len(methods) for content in project_map.values() 
                       for methods in content['classes'].values())
    total_functions = sum(len(content['functions']) for content in project_map.values())
    
    print(f"SUMMARY: {len(project_map)} files, {total_classes} classes, {total_methods} methods, {total_functions} functions")

if __name__ == "__main__":
    generate_report()