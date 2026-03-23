# Initialize Git (run on your Mac)

Cursor’s environment couldn’t create `.git` here, so run these in **Terminal** once:

```bash
cd ~/DNR_Well_Viewer_Full_Demo

git init -b main
git add -A
git status    # review what will be committed
git commit -m "Initial commit: C&J Well Viewer + build scripts"
```

Optional — add GitHub:

```bash
gh repo create c-j-well-viewer --private --source=. --push
# or create an empty repo on github.com, then:
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

**Already ignored** (see `.gitignore`): `.vercel`, `.env*.local`, large `dnr_wells_*.csv`, Python cruft, `.DS_Store`.
