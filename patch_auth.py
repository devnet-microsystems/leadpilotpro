import re

with open("web_server.py", "r") as f:
    content = f.read()

unauthenticated = ["read_root", "login", "logout", "startup_event"]

def replacer(match):
    decorator = match.group(1)
    func_def = match.group(2)
    func_name = match.group(3)
    args = match.group(4)
    
    if func_name in unauthenticated:
        return match.group(0)
        
    if "Depends(get_current_user)" in args:
        return match.group(0)
        
    if args.strip():
        new_args = args + ", user: dict = Depends(get_current_user)"
    else:
        new_args = "user: dict = Depends(get_current_user)"
        
    return f"{decorator}\n{func_def}{func_name}({new_args}):"

pattern = r"(@app\.(?:get|post|put|delete|patch|on_event)\(.*?\))\n(async def |def )([a-zA-Z0-9_]+)\((.*?)\):"
new_content = re.sub(pattern, replacer, content)

with open("web_server.py", "w") as f:
    f.write(new_content)
