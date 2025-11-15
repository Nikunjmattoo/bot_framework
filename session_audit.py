#!/usr/bin/env python3
"""
Session Management Audit Script

Analyzes Python files to identify session management patterns and potential violations.

Usage:
    python session_audit.py /path/to/your/codebase
    python session_audit.py /path/to/your/codebase --output report.json
"""

import ast
import os
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import json


@dataclass
class FunctionInfo:
    file_path: str
    function_name: str
    line_number: int
    is_async: bool
    has_session_param: bool
    creates_session: bool
    session_creation_lines: List[int]
    is_method: bool
    class_name: Optional[str]
    decorator_names: List[str]


class SessionAuditor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.functions: List[FunctionInfo] = []
        self.current_class = None
        
    def visit_ClassDef(self, node):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_FunctionDef(self, node):
        self._process_function(node, is_async=False)
        
    def visit_AsyncFunctionDef(self, node):
        self._process_function(node, is_async=True)
        
    def _process_function(self, node, is_async: bool):
        # Check if function has session parameter
        has_session_param = any(
            arg.arg == 'session' or 
            (hasattr(arg, 'annotation') and 
             arg.annotation and 
             self._is_session_type(arg.annotation))
            for arg in node.args.args
        )
        
        # Check if function creates sessions
        creates_session = False
        session_creation_lines = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.With) or isinstance(child, ast.AsyncWith):
                # Check for context manager: async with get_session() as session
                for item in child.items:
                    if self._is_session_creation(item.context_expr):
                        creates_session = True
                        session_creation_lines.append(child.lineno)
            
            elif isinstance(child, ast.Call):
                # Check for direct calls: session = get_session()
                if self._is_session_creation(child):
                    creates_session = True
                    session_creation_lines.append(child.lineno)
        
        # Get decorator names
        decorator_names = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorator_names.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                decorator_names.append(decorator.attr)
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    decorator_names.append(decorator.func.id)
                elif isinstance(decorator.func, ast.Attribute):
                    decorator_names.append(decorator.func.attr)
        
        func_info = FunctionInfo(
            file_path=self.file_path,
            function_name=node.name,
            line_number=node.lineno,
            is_async=is_async,
            has_session_param=has_session_param,
            creates_session=creates_session,
            session_creation_lines=session_creation_lines,
            is_method=self.current_class is not None,
            class_name=self.current_class,
            decorator_names=decorator_names
        )
        
        self.functions.append(func_info)
        
        # Continue visiting nested functions
        self.generic_visit(node)
    
    def _is_session_type(self, annotation):
        """Check if annotation indicates a session type"""
        if isinstance(annotation, ast.Name):
            return annotation.id in ['AsyncSession', 'Session']
        elif isinstance(annotation, ast.Subscript):
            # Handle Optional[AsyncSession], etc.
            if isinstance(annotation.value, ast.Name):
                return annotation.value.id in ['AsyncSession', 'Session']
        return False
    
    def _is_session_creation(self, node):
        """Check if node represents session creation"""
        if isinstance(node, ast.Call):
            # get_session() or AsyncSession()
            if isinstance(node.func, ast.Name):
                return node.func.id in ['get_session', 'AsyncSession', 'Session', 'get_db']
            # db.get_session()
            elif isinstance(node.func, ast.Attribute):
                return node.func.attr in ['get_session', 'AsyncSession', 'Session']
        return False


def analyze_file(file_path: Path) -> List[FunctionInfo]:
    """Analyze a single Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(file_path))
        auditor = SessionAuditor(str(file_path))
        auditor.visit(tree)
        return auditor.functions
    except SyntaxError as e:
        print(f"⚠️  Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}", file=sys.stderr)
        return []


def analyze_directory(root_path: Path) -> List[FunctionInfo]:
    """Recursively analyze all Python files in directory"""
    all_functions = []
    
    for file_path in root_path.rglob("*.py"):
        # Skip common directories
        if any(part in file_path.parts for part in ['.venv', 'venv', '__pycache__', '.git', 'node_modules']):
            continue
            
        functions = analyze_file(file_path)
        all_functions.extend(functions)
    
    return all_functions


def classify_violations(functions: List[FunctionInfo]) -> Dict[str, List[FunctionInfo]]:
    """Classify functions into violation categories"""
    classifications = {
        'hot_path_violations': [],      # Should receive session but creates own
        'cold_path_violations': [],     # Should create session but receives injected
        'endpoint_handlers': [],        # FastAPI/Flask endpoints (should create session)
        'proper_hot_path': [],          # Correctly receives session
        'proper_cold_path': [],         # Correctly creates session
        'no_session_usage': [],         # Doesn't use sessions at all
        'ambiguous': []                 # Needs human review
    }
    
    for func in functions:
        # Skip private/dunder methods
        if func.function_name.startswith('_') and not func.function_name.startswith('__'):
            continue
        
        # Endpoint handlers (FastAPI, Flask, etc.)
        is_endpoint = any(dec in ['post', 'get', 'put', 'delete', 'patch', 'route', 'app.route'] 
                         for dec in func.decorator_names)
        
        # Background task indicators
        is_background = any(keyword in func.function_name.lower() 
                           for keyword in ['background', 'task', 'job', 'worker', 'scheduled'])
        
        # No session usage at all
        if not func.has_session_param and not func.creates_session:
            classifications['no_session_usage'].append(func)
            continue
        
        # Endpoint handlers - should create session via dependency injection
        if is_endpoint:
            classifications['endpoint_handlers'].append(func)
            continue
        
        # Both receives AND creates - this is suspicious
        if func.has_session_param and func.creates_session:
            classifications['ambiguous'].append(func)
            continue
        
        # Async functions are likely cold path
        if func.is_async:
            if is_background:
                # Background tasks should create their own session
                if func.creates_session and not func.has_session_param:
                    classifications['proper_cold_path'].append(func)
                elif func.has_session_param and not func.creates_session:
                    classifications['cold_path_violations'].append(func)
                else:
                    classifications['ambiguous'].append(func)
            else:
                # Regular async functions - ambiguous without context
                # Could be hot path (orchestrator) or cold path (background)
                if func.has_session_param and not func.creates_session:
                    classifications['proper_hot_path'].append(func)
                elif func.creates_session and not func.has_session_param:
                    classifications['proper_cold_path'].append(func)
                else:
                    classifications['ambiguous'].append(func)
        else:
            # Sync functions - typically hot path
            if func.has_session_param and not func.creates_session:
                classifications['proper_hot_path'].append(func)
            elif func.creates_session and not func.has_session_param:
                # Sync function creating session - might be entry point or violation
                classifications['ambiguous'].append(func)
    
    return classifications


def print_report(classifications: Dict[str, List[FunctionInfo]]):
    """Print human-readable report"""
    print("\n" + "="*80)
    print("SESSION MANAGEMENT AUDIT REPORT")
    print("="*80)
    
    # Summary
    total = sum(len(funcs) for funcs in classifications.values())
    print(f"\nTotal functions analyzed: {total}")
    print(f"  ✅ Proper hot path: {len(classifications['proper_hot_path'])}")
    print(f"  ✅ Proper cold path: {len(classifications['proper_cold_path'])}")
    print(f"  ❌ Hot path violations: {len(classifications['hot_path_violations'])}")
    print(f"  ❌ Cold path violations: {len(classifications['cold_path_violations'])}")
    print(f"  🔍 Ambiguous (needs review): {len(classifications['ambiguous'])}")
    print(f"  📍 Endpoint handlers: {len(classifications['endpoint_handlers'])}")
    print(f"  ⚪ No session usage: {len(classifications['no_session_usage'])}")
    
    # Hot path violations
    if classifications['hot_path_violations']:
        print("\n" + "-"*80)
        print("❌ HOT PATH VIOLATIONS")
        print("   (Functions that should receive session but create their own)")
        print("-"*80)
        for func in classifications['hot_path_violations']:
            print(f"\n📁 {func.file_path}:{func.line_number}")
            print(f"   Function: {func.class_name + '.' if func.class_name else ''}{func.function_name}")
            print(f"   Type: {'async' if func.is_async else 'sync'}")
            print(f"   Creates session at lines: {func.session_creation_lines}")
    
    # Cold path violations
    if classifications['cold_path_violations']:
        print("\n" + "-"*80)
        print("❌ COLD PATH VIOLATIONS")
        print("   (Background/async functions that receive session instead of creating)")
        print("-"*80)
        for func in classifications['cold_path_violations']:
            print(f"\n📁 {func.file_path}:{func.line_number}")
            print(f"   Function: {func.class_name + '.' if func.class_name else ''}{func.function_name}")
            print(f"   Type: {'async' if func.is_async else 'sync'}")
    
    # Ambiguous cases
    if classifications['ambiguous']:
        print("\n" + "-"*80)
        print("🔍 AMBIGUOUS CASES (Need Human Review)")
        print("   (Functions that need context to determine if pattern is correct)")
        print("-"*80)
        for func in classifications['ambiguous']:
            print(f"\n📁 {func.file_path}:{func.line_number}")
            print(f"   Function: {func.class_name + '.' if func.class_name else ''}{func.function_name}")
            print(f"   Type: {'async' if func.is_async else 'sync'}")
            print(f"   Has session param: {func.has_session_param}")
            print(f"   Creates session: {func.creates_session}")
            if func.creates_session:
                print(f"   Creates at lines: {func.session_creation_lines}")
    
    # Endpoint handlers
    if classifications['endpoint_handlers']:
        print("\n" + "-"*80)
        print("📍 ENDPOINT HANDLERS")
        print("   (Should use dependency injection for session)")
        print("-"*80)
        for func in classifications['endpoint_handlers']:
            print(f"\n📁 {func.file_path}:{func.line_number}")
            print(f"   Endpoint: {func.function_name}")
            print(f"   Decorators: {', '.join(func.decorator_names)}")
            print(f"   Has session param: {func.has_session_param}")
            print(f"   Creates session: {func.creates_session}")
    
    print("\n" + "="*80)
    print("END OF REPORT")
    print("="*80 + "\n")


def print_summary(classifications: Dict[str, List[FunctionInfo]]):
    """Print concise summary of files with issues"""
    print("\n" + "="*80)
    print("FILES WITH ISSUES - SUMMARY")
    print("="*80)
    
    issues = {
        'hot_path_violations': '❌ HOT PATH VIOLATION',
        'cold_path_violations': '❌ COLD PATH VIOLATION',
        'ambiguous': '🔍 AMBIGUOUS'
    }
    
    file_issues = {}
    
    for category, label in issues.items():
        for func in classifications[category]:
            key = func.file_path
            if key not in file_issues:
                file_issues[key] = []
            file_issues[key].append({
                'category': label,
                'function': f"{func.class_name + '.' if func.class_name else ''}{func.function_name}",
                'line': func.line_number
            })
    
    if not file_issues:
        print("\n✅ No violations found! All session management looks good.\n")
        return
    
    print(f"\n📊 {len(file_issues)} files need attention:\n")
    
    for file_path in sorted(file_issues.keys()):
        print(f"\n📁 {file_path}")
        for issue in file_issues[file_path]:
            print(f"   {issue['category']}: {issue['function']} (line {issue['line']})")
    
    print("\n" + "="*80)
    print(f"Total files with issues: {len(file_issues)}")
    print("="*80 + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python session_audit.py /path/to/codebase [--output report.json] [--summary]")
        print("\nOptions:")
        print("  --output FILE    Save detailed JSON report")
        print("  --summary        Show only files with issues (concise view)")
        sys.exit(1)
    
    root_path = Path(sys.argv[1])
    if not root_path.exists():
        print(f"Error: Path {root_path} does not exist")
        sys.exit(1)
    
    print(f"🔍 Analyzing codebase at: {root_path}")
    print("   This may take a moment...\n")
    
    # Analyze all files
    all_functions = analyze_directory(root_path)
    
    if not all_functions:
        print("⚠️  No Python files found or no functions to analyze")
        sys.exit(0)
    
    # Classify violations
    classifications = classify_violations(all_functions)
    
    # Check if summary mode
    if '--summary' in sys.argv:
        print_summary(classifications)
    else:
        # Print full report
        print_report(classifications)
    
    # Save JSON output if requested
    if '--output' in sys.argv:
        output_idx = sys.argv.index('--output') + 1
        if output_idx < len(sys.argv):
            output_file = sys.argv[output_idx]
            output_data = {
                category: [asdict(func) for func in funcs]
                for category, funcs in classifications.items()
            }
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\n📄 Detailed report saved to: {output_file}")


if __name__ == '__main__':
    main()