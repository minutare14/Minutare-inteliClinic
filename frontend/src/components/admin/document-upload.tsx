"use client";

import { useState } from "react";
import { uploadDocument } from "@/lib/api";

interface DocumentUploadProps {
  onUploadComplete?: () => void;
}

export function DocumentUpload({ onUploadComplete }: DocumentUploadProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [category, setCategory] = useState("outro");
  const [title, setTitle] = useState("");

  const categories = [
    { value: "convenio", label: "Convênio" },
    { value: "protocolo", label: "Protocolo" },
    { value: "faq", label: "FAQ" },
    { value: "manual", label: "Manual" },
    { value: "tabela", label: "Tabela" },
    { value: "outro", label: "Outro" },
  ];

  async function handleFile(file: File) {
    setError(null);
    setSuccess(null);

    const validTypes = ["application/pdf", "text/markdown", "text/x-markdown"];
    if (!validTypes.includes(file.type)) {
      setError("Tipo de arquivo não suportado. Use PDF ou Markdown.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError("Arquivo muito grande. Máximo 10MB.");
      return;
    }

    setUploading(true);
    try {
      const result = await uploadDocument(file, category, title || null);
      setSuccess(`Documento "${result.title}" enviado com sucesso. ${result.chunks_created} chunks criados.`);
      if (onUploadComplete) onUploadComplete();
      setTitle("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="space-y-4">
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-gray-400"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".pdf,.md,.markdown"
          onChange={handleChange}
          className="hidden"
          id="file-upload"
          disabled={uploading}
        />
        <label htmlFor="file-upload" className="cursor-pointer">
          <div className="text-gray-600 mb-2">
            {uploading ? "Enviando..." : "Arraste um arquivo ou clique para selecionar"}
          </div>
          <div className="text-sm text-gray-400">PDF ou Markdown, máximo 10MB</div>
        </label>
      </div>

      <div className="flex gap-4">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
          disabled={uploading}
        >
          {categories.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Título do documento (opcional)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="flex-1 border rounded px-3 py-2 text-sm"
          disabled={uploading}
        />
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 text-sm p-3 rounded">{error}</div>
      )}
      {success && (
        <div className="bg-green-50 text-green-700 text-sm p-3 rounded">{success}</div>
      )}
    </div>
  );
}