// Same-origin API proxy for the development server (Create React App loads this file automatically).
// The API paths are forwarded to the backend here instead of through package.json "proxy", because the CRA
// dev server adds "Access-Control-Allow-Origin: *" to the responses it serves itself; this proxy ends the
// request first, so API responses carry no CORS headers and other websites cannot read them from a browser.
// package.json still sets "proxy": CRA only checks the Host header (DNS-rebinding protection) when it is set.
// http-proxy-middleware is the version react-scripts already installs (CRA's documented setupProxy approach).
const { createProxyMiddleware } = require("http-proxy-middleware");

const API_PATHS = ["/courses", "/options", "/health", "/agent"];

module.exports = function setupProxy(app) {
  app.use(createProxyMiddleware(API_PATHS, {
    target: process.env.BACKEND_URL || "http://backend:8000",  // Docker service name on the internal network
    logLevel: "warn",
  }));
};
