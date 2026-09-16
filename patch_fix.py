import re

with open("imap_poller.py", "r") as f:
    content = f.read()

content = content.replace(
    "if cand == imap_user.lower() or cand == sender_email: continue",
    "if cand == imap_user.lower(): continue"
)

with open("imap_poller.py", "w") as f:
    f.write(content)
print("Done fixing imap_poller.py")
