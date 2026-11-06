# Frontend (Angular)

This Angular app lives in `frontend/app` and is wired to the Feature 1 FastAPI endpoints.

## Run
```powershell
cd frontend\app
npm.cmd install
npm.cmd start
```

Open: `http://localhost:4200`

## Build Validation
```powershell
npm.cmd run build
```

## Flow in UI
1. Bootstrap a new institution or sign in to an existing one
2. Open the workbench with the institution JWT
3. Create Property
4. Attach Agreement
5. Invite Owner
6. Register/Login as Owner in the workbench
7. Acknowledge as Owner
8. Refresh Property/Owners to verify activation
