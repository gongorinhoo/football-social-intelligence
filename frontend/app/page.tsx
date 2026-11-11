
import Link from "next/link";

const modules = [
  {
    title: "Kluby piłkarskie",
    description: "Lista monitorowanych profili TikTok",
    href: "/panel/kluby",
    icon: "⚽",
  },
  {
    title: "Dashboard",
    description: "Statystyki wyświetleń i obserwujących",
    href: "#",
    icon: "📊",
  },
  {
    title: "AI Predictor",
    description: "Analiza potencjału nowych materiałów",
    href: "#",
    icon: "🧠",
  },
  {
    title: "Viral Radar",
    description: "Wykrywanie najpopularniejszych filmów",
    href: "#",
    icon: "🚀",
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#090d12] px-6 py-12 text-white">
      <div className="mx-auto max-w-6xl">

        <header className="mb-12 border-b border-white/10 pb-8">
          <p className="mb-2 text-sm font-semibold tracking-widest text-emerald-400">
            FOOTBALL SOCIAL INTELLIGENCE
          </p>

          <h1 className="text-4xl font-bold">
            Dashboard
          </h1>

          <p className="mt-4 text-slate-400">
            Platforma analityczna polskich klubów piłkarskich.
          </p>
          <Link
            href="/panel/kluby"
            className="mt-6 inline-block rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-black transition hover:bg-emerald-400"
          >
            Przejdź do listy klubów
          </Link>
        </header>

        <div className="mb-10 grid gap-5 md:grid-cols-3">
          <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
            <p className="text-sm text-slate-400">Monitorowane kluby</p>
            <p className="mt-3 text-4xl font-bold text-emerald-400">
              49
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
            <p className="text-sm text-slate-400">Monitorowane filmy</p>
            <p className="mt-3 text-4xl font-bold">
              —
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
            <p className="text-sm text-slate-400">Wyświetlenia</p>
            <p className="mt-3 text-4xl font-bold">
              —
            </p>
          </div>
        </div>

        <section>
          <h2 className="mb-6 text-2xl font-semibold">
            Moduły platformy
          </h2>

          <div className="grid gap-5 md:grid-cols-2">
            {modules.map((module) => (
              <Link
                key={module.title}
                href={module.href}
                className="rounded-xl border border-white/10 bg-[#111923] p-6 transition hover:border-emerald-500/50"
              >
                <div className="mb-4 text-3xl">
                  {module.icon}
                </div>

                <h3 className="text-lg font-semibold">
                  {module.title}
                </h3>

                <p className="mt-2 text-sm text-slate-400">
                  {module.description}
                </p>
              </Link>
            ))}
          </div>
        </section>

        <footer className="mt-16 border-t border-white/10 pt-6 text-sm text-slate-500">
          Football Social Intelligence • Development v0.4
        </footer>

      </div>
    </main>
  );
}
