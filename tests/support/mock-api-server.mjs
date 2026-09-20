import http from "node:http";
import { createMockApiHandler } from "../../traffic-app/mocks/api.mjs";

const PORT = Number(process.env.PLAYWRIGHT_MOCK_API_PORT || "8787");
const server = http.createServer(createMockApiHandler());

server.listen(PORT, "127.0.0.1", () => {
  process.stdout.write(`Mock API listening on http://127.0.0.1:${PORT}\n`);
});
