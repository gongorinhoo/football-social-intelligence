
import Link from "next/link";
import { notFound } from "next/navigation";
import FollowersPanel from "./FollowersPanel";

type Club = {
  id: number;
  name: string;
  tiktok_handle: string;
  league: string | null;
  is_active: boolean;
  created_at: string;
};

type PageProps = {
  params: Promise<{ id: string }>;
};

// Pobieramy dane konkretnego klubu z FastAPI
async function getClub(id: string): Promise<Club | null> {
  const apiUrl =
    process.env.FSI_API_URL || "http://127.0.0.1:8000";

  const response = await fetch(
    `${apiUrl}/api/clubs/${id}`,
    { cache: "no-store" }
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(
      `Błąd API: ${response.status}`
    );
  }

  return response.json();
}

// Karta statystyki – wykorzystamy ją później
// również w innych częściach aplikacji
function StatCard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: string;
  subtitle: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-4 text-3xl font-semibold">{value}</p>
      <p className="mt-2 text-xs text-slate-500">
        {subtitle}
      </p>
    </div>
  );
}

export default async function ClubProfilePage({
  params,
}: PageProps) {
  const { id } = await params;

  // Walidacja ID
  if (!/^[1-9]\d*$/.test(id)) {
    notFound();
  }

  const club = await getClub(id);

  if (!club) {
    notFound();
  }

  const tiktokUrl =
    `https://www.tiktok.com/@${encodeURIComponent(club.tiktok_handle)}`;

  return (
    <main className="min-h-screen bg-[#090d12] px-6 py-10 text-slate-100">
      <div className="mx-auto max-w-7xl">

        {/* Nawigacja */}
        <div className="mb-8">
          <Link
            href="/panel/kluby"
            className="text-sm text-slate-400 transition hover:text-emerald-400"
          >
            ← Powrót do klubów
          </Link>
        </div>

        {/* Nagłówek profilu */}
        <header className="mb-10 border-b border-white/10 pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-emerald-400">
            Football Social Intelligence / Club Profile
          </p>

          <div className="flex flex-wrap items-start justify-between gap-5">
            <div>
              <h1 className="text-4xl font-bold">
                {club.name}
              </h1>

              <a
                href={tiktokUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-block text-sm text-emerald-400 hover:text-emerald-300"
              >
                @{club.tiktok_handle} ↗
              </a>

              <p className="mt-3 text-sm text-slate-400">
                {club.league || "Liga nieprzypisana"}
              </p>
            </div>

            <div
              className={`rounded-full border px-4 py-2 text-sm ${
                club.is_active
                  ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                  : "border-slate-500/20 bg-slate-500/10 text-slate-400"
              }`}
            >
              {club.is_active ? "● Aktywny" : "● Nieaktywny"}
            </div>
          </div>
        </header>

        {/* Informacje o profilu */}
        <section className="mb-10">
          <h2 className="mb-5 text-xl font-semibold">
            Informacje o profilu
          </h2>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
              <p className="text-sm text-slate-400">
                Identyfikator klubu
              </p>
              <p className="mt-3 text-xl font-semibold">
                #{club.id}
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
              <p className="text-sm text-slate-400">
                Platforma
              </p>
              <p className="mt-3 text-xl font-semibold">
                TikTok
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
              <p className="text-sm text-slate-400">
                Data dodania do bazy
              </p>
              <p className="mt-3 text-xl font-semibold">
                {club.created_at.slice(0, 10)}
              </p>
            </div>
          </div>
        </section>

        {/* Statystyki – uzupełnimy danymi TikTok */}
        <section className="mb-10">
          <h2 className="mb-5 text-xl font-semibold">
            Statystyki TikTok
          </h2>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              title="Obserwujący"
              value="—"
              subtitle="Oczekiwanie na pierwszy pomiar"
            />

            <StatCard
              title="Wyświetlenia"
              value="—"
              subtitle="Brak danych o filmach"
            />

            <StatCard
              title="Opublikowane filmy"
              value="—"
              subtitle="Monitoring jeszcze nieuruchomiony"
            />

            <StatCard
              title="Polubienia"
              value="—"
              subtitle="Oczekiwanie na dane"
            />
          </div>
        </section>

        {/* Miejsce na historię */}
        <FollowersPanel clubId={club.id} />

        {/* Przyszłe moduły */}
        <section className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
            <p className="mb-2 text-sm text-emerald-400">
              CONTENT ANALYTICS
            </p>

            <h3 className="text-xl font-semibold">
              Najpopularniejsze filmy
            </h3>

            <p className="mt-3 text-sm text-slate-400">
              W tym miejscu pojawi się ranking
              najlepszych publikacji klubu.
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
            <p className="mb-2 text-sm text-emerald-400">
              ARTIFICIAL INTELLIGENCE
            </p>

            <h3 className="text-xl font-semibold">
              AI Club Intelligence
            </h3>

            <p className="mt-3 text-sm text-slate-400">
              Analiza skuteczności formatów oraz
              rekomendacje przyszłych publikacji.
            </p>
          </div>
        </section>

        <footer className="mt-14 border-t border-white/10 pt-6 text-xs text-slate-500">
          Football Social Intelligence • Club Profile v0.5
        </footer>
      </div>
    </main>
  );
}
