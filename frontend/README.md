# Frontend TS/LSP Setup

This project includes a TypeScript language-server setup for the Angular frontend workspace in `frontend/`.

## Install
From repo root:

```powershell
cd frontend
npm install
```

## Validate TypeScript Project
```powershell
npm run lsp:check
```

## Start Language Server Manually (optional)
```powershell
npm run lsp:server
```

## Notes
- VS Code workspace settings point `typescript.tsdk` to `frontend/node_modules/typescript/lib`.
- `tsconfig.json` is strict by default.