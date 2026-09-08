import glob
for f in glob.glob('backend/tests/test_*.py'):
    if 'test_seed' in f: continue
    with open(f, 'r') as file:
        content = file.read()
    if 'StaticPool' not in content:
        content = content.replace('from sqlalchemy import create_engine', 'from sqlalchemy import create_engine\nfrom sqlalchemy.pool import StaticPool')
        content = content.replace('connect_args={"check_same_thread": False}', 'connect_args={"check_same_thread": False}, poolclass=StaticPool')
        with open(f, 'w') as file:
            file.write(content)
        print(f'Patched {f}')
