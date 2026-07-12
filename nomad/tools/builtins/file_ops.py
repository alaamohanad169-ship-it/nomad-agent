"""File tools — read, write, search files."""
import json
import os
import re
from pathlib import Path

from nomad.tools.registry import registry, ToolSchema, ToolRisk


async def read_file(path: str, offset: int = 1, limit: int = 200) -> str:
    """Read a file with line numbers."""
    p = Path(path).expanduser().resolve()
    
    if not p.exists():
        return json.dumps({"error": f"File not found: {path}"})
    if not p.is_file():
        return json.dumps({"error": f"Not a file: {path}"})
    
    # Check file size (skip huge files)
    size_mb = p.stat().st_size / 1024 / 1024
    if size_mb > 10:
        return json.dumps({"error": f"File too large: {size_mb:.1f}MB. Use terminal for large files."})
    
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        total = len(lines)
        
        # Apply offset/limit
        start = max(0, offset - 1)
        end = min(total, start + limit)
        selected = lines[start:end]
        
        # Add line numbers
        numbered = [f"{i+start+1:5d} | {line}" for i, line in enumerate(selected)]
        
        return json.dumps({
            "content": "\n".join(numbered),
            "total_lines": total,
            "offset": start + 1,
            "limit": len(selected),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def write_file(path: str, content: str) -> str:
    """Write content to a file (creates parent dirs)."""
    p = Path(path).expanduser().resolve()
    
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return json.dumps({
            "success": True,
            "path": str(p),
            "bytes": len(content.encode()),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def search_files(pattern: str, path: str = ".", file_glob: str = None) -> str:
    """Search file contents with regex."""
    search_path = Path(path).expanduser().resolve()
    
    if not search_path.exists():
        return json.dumps({"error": f"Path not found: {path}"})
    
    matches = []
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return json.dumps({"error": f"Invalid regex: {e}"})
    
    # Determine files to search
    if search_path.is_file():
        files = [search_path]
    else:
        files = list(search_path.rglob(file_glob or "*.py"))
        files = [f for f in files if f.is_file() and ".git" not in str(f)]
        files = files[:100]  # Cap file count
    
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    matches.append({
                        "file": str(filepath.relative_to(search_path.parent)),
                        "line": i,
                        "content": line.strip()[:200],
                    })
                    if len(matches) >= 50:
                        break
        except Exception:
            continue
        if len(matches) >= 50:
            break
    
    return json.dumps({"matches": matches, "total": len(matches)})


# Register tools
registry.register(ToolSchema(
    name="read_file",
    description="Read a file with line numbers. Returns content with line numbers, total lines.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
            "offset": {"type": "integer", "description": "Start line (1-indexed, default 1)"},
            "limit": {"type": "integer", "description": "Max lines to return (default 200)"},
        },
        "required": ["path"],
    },
    risk=ToolRisk.SAFE,
    handler=read_file,
))

registry.register(ToolSchema(
    name="write_file",
    description="Write content to a file. Creates parent directories. Overwrites existing content.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
    risk=ToolRisk.MODERATE,
    handler=write_file,
))

registry.register(ToolSchema(
    name="search_files",
    description="Search file contents with regex pattern. Returns matching lines with file paths and line numbers.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory or file to search (default: current)"},
            "file_glob": {"type": "string", "description": "File pattern filter (e.g. '*.py')"},
        },
        "required": ["pattern"],
    },
    risk=ToolRisk.SAFE,
    handler=search_files,
))
