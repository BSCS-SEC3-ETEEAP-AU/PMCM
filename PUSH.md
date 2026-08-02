# Push to GitHub — one-time step (run on YOUR machine)

The codebase is already initialized as a git repo with everything committed
to the `main` branch. Because the build environment has no GitHub credentials,
you push it from your own machine where you're already authenticated.

## Option A — repo is currently EMPTY on GitHub
```powershell
cd E:\ETEEAP\CLASSES\Thesis 1\THESIS-WEB-APP
git remote add origin https://github.com/BSCS-SEC3-ETEEAP-AU/PMCM.git
git branch -M main
git push -u origin main
```

## Option B — repo already has files on GitHub (e.g. a README you created)
```powershell
cd E:\ETEEAP\CLASSES\Thesis 1\THESIS-WEB-APP
git remote add origin https://github.com/BSCS-SEC3-ETEEAP-AU/PMCM.git
git pull origin main --allow-unrelated-histories   # if GitHub has content
git push -u origin main
```

That's it. After this, `git status` should be clean and the files will appear
on https://github.com/BSCS-SEC3-ETEEAP-AU/PMCM.

> Do NOT commit `.env` — it holds your Supabase password and is git-ignored.
> Only `.env.example` (the template) is committed.
