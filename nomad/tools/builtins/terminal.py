"""Terminal tool — run shell commands."""
import asyncio
import json
import os
import shutil

from nomad.tools.registry import registry, ToolSchema, ToolRisk


async def terminal(command: str, timeout: int = 30, cwd: str = None) -> str:
    """Execute a shell command and return output."""
    work_dir = cwd or os.getcwd()
    
    # Validate directory exists
    if not os.path.isdir(work_dir):
        return json.dumps({"error": f"Directory not found: {work_dir}"})
    
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return json.dumps({
                "error": f"Command timed out after {timeout}s",
                "command": command,
            })
        
        output = stdout.decode(errors="replace").strip()
        error = stderr.decode(errors="replace").strip()
        
        result = {
            "exit_code": proc.returncode,
            "output": output[:5000],  # Cap output
        }
        if error:
            result["stderr"] = error[:2000]
        
        return json.dumps(result)
    
    except Exception as e:
        return json.dumps({"error": str(e), "command": command})


# Register the tool
registry.register(ToolSchema(
    name="terminal",
    description="Execute a shell command. Use for system operations, git, package managers, building code. Returns stdout, stderr, and exit code.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds (default 30)",
                "default": 30,
            },
            "cwd": {
                "type": "string",
                "description": "Working directory (optional)",
            },
        },
        "required": ["command"],
    },
    risk=ToolRisk.DANGEROUS,
    handler=terminal,
))
