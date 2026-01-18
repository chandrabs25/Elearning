"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [status, setStatus] = useState("Checking Backend...");

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/health`)
      .then((res) => res.json())
      .then((data) => setStatus(`Backend Connected: ${data.status}`))
      .catch((err) => setStatus("Backend Disconnected"));
  }, []);

  return (
    <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center font-mono">
      <h1 className="text-4xl mb-4">Blank Slate</h1>
      <p className="text-zinc-500 mb-8">{status}</p>
      <a href="/tutor" className="px-8 py-4 bg-white text-black rounded-full font-bold hover:bg-zinc-200 transition">
        Start Learning Gravity
      </a>
    </div>
  );
}
