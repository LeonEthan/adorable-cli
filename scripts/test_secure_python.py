from adorable_cli.tools import create_secure_python_tools


def main():
    tools = create_secure_python_tools()
    print("=== Allowed: simple compute ===")
    out = tools.execute_python_code("print(sum([1,2,3,4]))")
    print(out)

    print("\n=== Allowed: numpy compute ===")
    code = "import numpy as np\nprint(np.sum(np.arange(5)))"
    out = tools.execute_python_code(code)
    print(out)

    print("\n=== Blocked: dangerous function eval() ===")
    out = tools.execute_python_code("eval('2+2')")
    print(out)

    print("\n=== Blocked: import subprocess ===")
    out = tools.execute_python_code("import subprocess\nprint('ok')")
    print(out)

    print("\n=== Blocked: file operation open() ===")
    out = tools.execute_python_code("open('/etc/hosts').read()")
    print(out)


if __name__ == "__main__":
    main()
