/**
 * Test Suite ID: TASK-FRT-202
 * Backlog Task: TASK-FRT-202
 */
import { ImageResponse } from "next/og";

export const alt = "C2Pro · Inteligencia documental para compras y contratos";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          alignItems: "flex-start",
          background: "#0B1F3A",
          color: "#F7F4ED",
          display: "flex",
          flexDirection: "column",
          fontFamily: "Georgia, serif",
          height: "100%",
          justifyContent: "space-between",
          padding: "80px",
          width: "100%",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "28px",
          }}
        >
          <div
            style={{
              color: "#8FD8CF",
              display: "flex",
              fontFamily: "Arial, sans-serif",
              fontSize: 24,
              letterSpacing: 3,
              textTransform: "uppercase",
            }}
          >
            Parte del ecosistema AI-Gen
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 112,
              lineHeight: 0.95,
            }}
          >
            C2Pro
          </div>
          <div
            style={{
              background: "#0F766E",
              display: "flex",
              height: 8,
              width: 180,
            }}
          />
          <div
            style={{
              display: "flex",
              fontFamily: "Arial, sans-serif",
              fontSize: 42,
              lineHeight: 1.25,
              maxWidth: 820,
            }}
          >
            Inteligencia documental para compras y contratos
          </div>
        </div>
        <div
          style={{
            alignSelf: "flex-end",
            color: "#8FD8CF",
            display: "flex",
            fontFamily: "Arial, sans-serif",
            fontSize: 26,
          }}
        >
          c2pro.io
        </div>
      </div>
    ),
    size,
  );
}
