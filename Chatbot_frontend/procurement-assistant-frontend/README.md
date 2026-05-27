# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
# Procurement RAG Chatbot - Frontend Requirements

This frontend is built with Vite + React. Standard installation uses `package.json`.
To install all dependencies, simply run:
```bash
npm install
```

## Primary Dependencies

If you need to install them manually, use this command:
```bash
npm install react@^19.2.0 react-dom@^19.2.0 react-markdown@^10.1.0
```

## Development Dependencies
If installing from scratch:
```bash
npm install -D @eslint/js@^9.39.1 @types/react@^19.2.2 @types/react-dom@^19.2.2 @vitejs/plugin-react@^5.1.0 eslint@^9.39.1 eslint-plugin-react-hooks@^7.0.1 eslint-plugin-react-refresh@^0.4.24 globals@^16.5.0 vite@^7.2.2
```
