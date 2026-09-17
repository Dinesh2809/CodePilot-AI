# CodePilot AI Frontend

The frontend foundation for the CodePilot AI workbench. It is built with React, TypeScript, and Vite.

## Local development

```bash
npm install
npm run dev
```

The current frontend provides the responsive application shell, repository upload, semantic search, grounded Q&A, review results, workflow states, and mobile layout.

## API configuration

Set `VITE_API_BASE_URL` before building the frontend. For local development, use `http://localhost:8000`; for the deployed backend, use the configured production API URL. Vite embeds this public base URL at build time. Do not place backend secrets in `VITE_` variables.
