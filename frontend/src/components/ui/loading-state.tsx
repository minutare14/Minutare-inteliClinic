export function LoadingState({ message = "Carregando..." }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3" />
      <span className="text-gray-500 text-sm">{message}</span>
    </div>
  );
}
