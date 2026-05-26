export function PageHeader({ title, description, icon: Icon, badges, actions, children }) {
  return (
    <div className="mb-4 sm:mb-6 pb-4 sm:pb-5 border-b border-sre-border">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-2.5 min-w-0">
          {Icon && (
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-indigo-600/15 border border-indigo-500/25 flex items-center justify-center shrink-0">
              <Icon size={17} className="text-indigo-400" />
            </div>
          )}
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-semibold text-white tracking-tight">{title}</h1>
            {description && (
              <p className="hidden sm:block text-sm text-gray-400 mt-1 leading-relaxed max-w-3xl">{description}</p>
            )}
          </div>
        </div>
        {(badges || actions) && (
          <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap shrink-0">
            {badges}
            {actions}
          </div>
        )}
      </div>
      {children && <div className="mt-3 sm:mt-4">{children}</div>}
    </div>
  );
}
