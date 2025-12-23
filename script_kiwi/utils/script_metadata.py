"""
Utility functions for extracting metadata from script files.
"""

import ast
import re
from typing import Dict, Any, List, Optional
from pathlib import Path


# Mapping of module names to their corresponding PyPI package names
# This is used when auto-extracting dependencies from imports
MODULE_TO_PACKAGE = {
    'git': 'GitPython',
    'bs4': 'beautifulsoup4',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',
    'sklearn': 'scikit-learn',
    'cv2': 'opencv-python',
    'PIL': 'Pillow',
    'openai': 'openai',
    'anthropic': 'anthropic',
    'supabase': 'supabase',
    'googleapiclient': 'google-api-python-client',
    'google_auth_oauthlib': 'google-auth-oauthlib',
}

# Mapping of package names to their corresponding import module names
# This is used when checking if a package is installed
PACKAGE_TO_MODULE = {v: k for k, v in MODULE_TO_PACKAGE.items()}


def extract_script_metadata(script_path: Path) -> Dict[str, Any]:
    """
    Extract metadata from a Python script file.
    
    Extracts:
    - Description from docstring
    - Dependencies from imports
    - Required env vars from os.getenv/os.environ usage
    - Input parameters from argparse or function signatures
    - Tech stack from imports
    
    Args:
        script_path: Path to the Python script file
        
    Returns:
        Dictionary with extracted metadata
    """
    metadata = {
        "description": None,
        "dependencies": [],
        "required_env_vars": [],
        "input_schema": {},
        "tech_stack": []
    }
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # If parsing fails, fall back to regex-based extraction
            return _extract_metadata_regex(content, metadata)
        
        # Extract docstring (module-level)
        # Handle both ast.Str (Python <3.8) and ast.Constant (Python 3.8+)
        if tree.body and isinstance(tree.body[0], ast.Expr):
            docstring_value = tree.body[0].value
            docstring = None
            if isinstance(docstring_value, ast.Str):  # Python <3.8
                docstring = docstring_value.s
            elif isinstance(docstring_value, ast.Constant) and isinstance(docstring_value.value, str):  # Python 3.8+
                docstring = docstring_value.value
            
            if docstring:
                # Extract description (first paragraph)
                lines = docstring.strip().split('\n')
                description_lines = []
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('Usage:') or line.startswith('Args:'):
                        break
                    description_lines.append(line)
                if description_lines:
                    metadata["description"] = ' '.join(description_lines).strip()
        
        # Extract imports and dependencies
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split('.')[0])
        
        # Convert imports to dependencies (filter out stdlib and internal modules)
        stdlib_modules = {
            'os', 'sys', 'json', 'time', 'datetime', 'pathlib', 'typing',
            'argparse', 'logging', 'collections', 'itertools', 'functools',
            'contextlib', 'io', 'shlex', 'subprocess', 'importlib', 'hashlib',
            're', 'math', 'random', 'string', 'urllib', 'http', 'email',
            'concurrent', 'threading', 'multiprocessing', 'asyncio', 'queue'
        }
        # Internal script-kiwi modules (not pip packages)
        internal_modules = {'lib'}
        
        skip_modules = stdlib_modules | internal_modules
        external_deps = [imp for imp in set(imports) if imp not in skip_modules]
        metadata["dependencies"] = [{"name": MODULE_TO_PACKAGE.get(dep, dep), "version": None} for dep in external_deps]
        metadata["tech_stack"] = list(set([MODULE_TO_PACKAGE.get(dep, dep) for dep in external_deps]))
        
        # Extract required env vars (look for os.getenv, os.environ, load_dotenv patterns)
        env_vars = set()
        for node in ast.walk(tree):
            # Look for os.getenv() calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'getenv' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'os':
                        if node.args:
                            # Handle both ast.Str (Python <3.8) and ast.Constant (Python 3.8+)
                            arg = node.args[0]
                            if isinstance(arg, ast.Str):
                                env_vars.add(arg.s)
                            elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                env_vars.add(arg.value)
                    elif node.func.attr == 'get' and isinstance(node.func.value, ast.Attribute):
                        # os.environ.get('KEY')
                        if isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == 'os':
                            if isinstance(node.func.value.attr, ast.Name) and node.func.value.attr.id == 'environ':
                                if node.args:
                                    arg = node.args[0]
                                    if isinstance(arg, ast.Str):
                                        env_vars.add(arg.s)
                                    elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                        env_vars.add(arg.value)
        
        # Also check for load_dotenv() which suggests .env file usage
        has_dotenv = any(
            isinstance(node, ast.ImportFrom) and node.module == 'dotenv'
            for node in ast.walk(tree)
        )
        if has_dotenv:
            # Look for common env var patterns in comments or strings
            env_pattern = r'(?:APIFY_API_TOKEN|API_KEY|DATABASE_URL|SUPABASE_URL|OPENAI_API_KEY)'
            matches = re.findall(env_pattern, content, re.IGNORECASE)
            env_vars.update(matches)
        
        metadata["required_env_vars"] = sorted(list(env_vars))
        
        # Extract input parameters from argparse
        input_schema = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'main':
                # Look for argparse.ArgumentParser usage
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Call):
                        if isinstance(stmt.func, ast.Attribute):
                            if stmt.func.attr == 'add_argument':
                                # Extract argument name and help
                                arg_name = None
                                arg_help = None
                                arg_type = None
                                arg_required = False
                                
                                for keyword in stmt.keywords:
                                    # Handle both ast.Str and ast.Constant for string values
                                    if keyword.arg == 'dest':
                                        if isinstance(keyword.value, ast.Str):
                                            arg_name = keyword.value.s
                                        elif isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                                            arg_name = keyword.value.value
                                    elif keyword.arg == 'help':
                                        if isinstance(keyword.value, ast.Str):
                                            arg_help = keyword.value.s
                                        elif isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                                            arg_help = keyword.value.value
                                    elif keyword.arg == 'type':
                                        if isinstance(keyword.value, ast.Name):
                                            arg_type = keyword.value.id
                                    elif keyword.arg == 'required':
                                        if isinstance(keyword.value, ast.Constant):
                                            arg_required = keyword.value.value
                                        elif isinstance(keyword.value, ast.NameConstant):  # Python <3.8 (True/False)
                                            arg_required = keyword.value.value
                                
                                # If no dest, use first positional arg (the flag name)
                                if not arg_name and stmt.args:
                                    arg0 = stmt.args[0]
                                    if isinstance(arg0, ast.Str):
                                        flag = arg0.s
                                    elif isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                                        flag = arg0.value
                                    else:
                                        flag = None
                                    
                                    if flag:
                                        # Convert --flag-name to flag_name
                                        arg_name = flag.lstrip('-').replace('-', '_')
                                
                                if arg_name:
                                    input_schema[arg_name] = {
                                        "type": arg_type or "string",
                                        "description": arg_help or "",
                                        "required": arg_required
                                    }
        
        # If no argparse args found, try to extract from function signature
        if not input_schema:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in ['execute', 'main']:
                    # Extract function parameters
                    for arg in node.args.args:
                        if arg.arg not in ['self', 'params']:
                            # Try to get type hint
                            arg_type = "string"
                            if arg.annotation:
                                if isinstance(arg.annotation, ast.Name):
                                    arg_type = arg.annotation.id.lower()
                                elif isinstance(arg.annotation, ast.Subscript):
                                    if isinstance(arg.annotation.value, ast.Name):
                                        arg_type = arg.annotation.value.id.lower()
                            
                            input_schema[arg.arg] = {
                                "type": arg_type,
                                "description": "",
                                "required": True  # Assume required if no default
                            }
                    
                    # Check for defaults to mark optional params
                    if node.args.defaults:
                        num_defaults = len(node.args.defaults)
                        num_args = len(node.args.args)
                        for i, default in enumerate(node.args.defaults):
                            arg_idx = num_args - num_defaults + i
                            if arg_idx < len(node.args.args):
                                arg_name = node.args.args[arg_idx].arg
                                if arg_name in input_schema:
                                    input_schema[arg_name]["required"] = False
        
        metadata["input_schema"] = input_schema
        
    except Exception as e:
        # If extraction fails, return minimal metadata
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to extract metadata from {script_path}: {e}")
    
    return metadata


def _extract_metadata_regex(content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback regex-based metadata extraction when AST parsing fails.
    """
    # Extract docstring
    docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
    if docstring_match:
        docstring = docstring_match.group(1).strip()
        # Get first paragraph
        first_para = docstring.split('\n\n')[0].replace('\n', ' ').strip()
        if first_para:
            metadata["description"] = first_para[:200]  # Limit length
    
    # Extract imports
    import_pattern = r'^(?:from\s+(\S+)\s+)?import\s+(\S+)'
    imports = set()
    for line in content.split('\n'):
        match = re.match(import_pattern, line.strip())
        if match:
            if match.group(1):  # from X import
                imports.add(match.group(1).split('.')[0])
            elif match.group(2):  # import X
                imports.add(match.group(2).split('.')[0])
    
    stdlib_modules = {
        'os', 'sys', 'json', 'time', 'datetime', 'pathlib', 'typing',
        'argparse', 'logging', 'collections', 'itertools', 'functools'
    }
    external_deps = [imp for imp in imports if imp not in stdlib_modules]
    metadata["dependencies"] = [{"name": MODULE_TO_PACKAGE.get(dep, dep), "version": None} for dep in external_deps]
    metadata["tech_stack"] = list(set([MODULE_TO_PACKAGE.get(dep, dep) for dep in external_deps]))
    
    # Extract env vars
    env_pattern = r"os\.getenv\(['\"](\w+)['\"]|os\.environ\.get\(['\"](\w+)['\"]"
    env_vars = set()
    for match in re.finditer(env_pattern, content):
        env_vars.add(match.group(1) or match.group(2))
    metadata["required_env_vars"] = sorted(list(env_vars))
    
    return metadata
