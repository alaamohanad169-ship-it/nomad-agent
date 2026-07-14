"""Code execution tool — run Python code safely."""
import asyncio
import json
import sys
import tempfile
import os

from nomad.tools.registry import registry, ToolSchema, ToolRisk


async def execute_code(code: str, timeout: int = 30) -> str:
    """Execute Python code in a subprocess and return output."""
    # Write code to a temp file
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, encoding='utf-8'
    ) as f:
        f.write(code)
        temp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, temp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
                "error": f"Code execution timed out after {timeout}s",
                "exit_code": -1,
            })

        output = stdout.decode(errors="replace").strip()
        error = stderr.decode(errors="replace").strip()

        result = {
            "exit_code": proc.returncode,
            "output": output[:5000],
        }
        if error:
            result["stderr"] = error[:2000]

        return json.dumps(result)

    finally:
        os.unlink(temp_path)


# Register the tool
registry.register(ToolSchema(
    name="execute_code",
    description="Execute Python code and return output. Use for calculations, data processing, testing ideas. Returns stdout, stderr, and exit code.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds (default 30)",
                "default": 30,
            },
        },
        "required": ["code"],
    },
    risk=ToolRisk.DANGEROUS,
    handler=execute_code,
))
