# Seminary Frontend Development Guide

## Development Mode (`yarn dev`)

When running the frontend in development mode, you **MUST** access the application through the Frappe backend, not directly through the Vite dev server.

### Correct Access Method:
1. Start the Vite dev server:
   ```bash
   cd frontend
   yarn dev
   ```
   This starts Vite on port 8080

2. Ensure Frappe is running (bench start or similar)
   Frappe runs on port 8000

3. **Access the app at:** `http://your-site:8000/seminary/`
   - ✅ Correct: `http://ps:8000/seminary/` (or whatever your site name is)
   - ❌ Wrong: `http://localhost:8080` (this bypasses Frappe authentication)

### Why?
- The frontend requires Frappe session cookies for authentication
- Socket.IO connections need valid Frappe sessions
- The `frappe-ui/vite` plugin proxies requests between Vite (8080) and Frappe (8000)
- When you access through port 8000, Frappe handles authentication and proxies to Vite for hot-reload

### How It Works:
```
Browser → http://ps:8000/seminary/ 
       ↓
    Frappe Backend (port 8000)
       - Handles authentication
       - Injects boot data & session
       - Serves index.html with Jinja templates
       ↓
    Vite Dev Server (port 8080)
       - Provides hot module replacement
       - Serves source files (/src/main.js, etc.)
```

## Production Mode (`yarn build`)

In production, everything is bundled and served through Frappe:

```bash
cd frontend
yarn build
```

Access at: `http://your-site:8000/seminary/`

The built files are placed in `../seminary/public/frontend/` and served as static assets.

## Troubleshooting

### "Unauthorized" Socket.IO Error in Dev Mode
- Make sure you're accessing through port 8000, not 8080
- Clear browser cookies and cache
- Ensure you're logged into Frappe first

### Port 8080 Redirects to Desk
- This is expected! Port 8080 is for the Vite dev server only
- Always use port 8000 (Frappe) for actual app access

### Hot Reload Not Working
- Ensure Vite dev server is running (`yarn dev`)
- Check that Frappe can proxy to port 8080
- Check firewall/network settings if on WSL or remote server
