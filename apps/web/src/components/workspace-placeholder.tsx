export function WorkspacePlaceholder({ name, arrives }: { name: string; arrives: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
      <h1 className="text-xl font-semibold">{name} workspace</h1>
      <p className="mt-2 text-sm text-slate-600">{arrives}</p>
    </div>
  );
}
