export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-sre-border bg-sre-surface/40 px-8 py-12 text-center min-h-[280px]">
      {Icon && (
        <div className="w-12 h-12 rounded-xl bg-gray-800/80 border border-gray-700 flex items-center justify-center mb-4">
          <Icon size={22} className="text-gray-500" />
        </div>
      )}
      <p className="text-sm font-medium text-gray-300">{title}</p>
      {description && (
        <p className="text-xs text-gray-500 mt-2 max-w-sm leading-relaxed">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
