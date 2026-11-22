import subprocess

out = subprocess.run(
    ["docker", "inspect", "career-api", "--format",
     "{{range .Config.Env}}{{.}}\n{{end}}"],
    capture_output=True, text=True, check=True,
)
lines = [l for l in out.stdout.splitlines()
         if ("JSEARCH" in l or "DATABASE_URL" in l or "AI_PROVIDER" in l
             or "APISUBMIT" in l) and "=" in l]
for l in lines:
    name, _, val = l.partition("=")
    print(f"{name}=<set: {bool(val)}>")
