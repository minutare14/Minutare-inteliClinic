import type { Message } from "@/lib/types";
import { formatDateTime } from "@/lib/formatters";

export function MessageBubble({ message }: { message: Message }) {
  const isInbound = message.direction === "inbound";
  return (
    <div className={`flex ${isInbound ? "justify-start" : "justify-end"} mb-3`}>
      <div
        className={`max-w-[75%] rounded-lg px-4 py-2.5 text-sm ${
          isInbound
            ? "bg-gray-100 text-gray-800"
            : "bg-blue-600 text-white"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        <p
          className={`text-[10px] mt-1 ${
            isInbound ? "text-gray-400" : "text-blue-200"
          }`}
        >
          {formatDateTime(message.created_at)}
        </p>
      </div>
    </div>
  );
}
