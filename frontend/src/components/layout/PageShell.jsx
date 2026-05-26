export function PageShell({ children, constrained = false, className = "" }) {
  return (
    <div
      className={`px-3 sm:px-6 py-4 sm:py-6 w-full ${constrained ? "max-w-7xl mx-auto" : ""} ${className}`}
    >
      {children}
    </div>
  );
}
