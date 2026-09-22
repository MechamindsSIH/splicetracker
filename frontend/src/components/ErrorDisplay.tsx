export default function ErrorDisplay({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="text-red-500 text-lg mb-2">Error</div>
      <p className="text-sm text-slate-600 mb-4">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="text-sm px-4 py-1.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100">
          Retry
        </button>
      )}
    </div>
  );
}
