import ClubTable from "./ClubTable";



type Club = {
  id: number;
  name: string;
  tiktok_handle: string;
  league: string | null;
  is_active: boolean;
};

async function getClubs(): Promise<Club[]> {
  const apiUrl =
    process.env.FSI_API_URL || "http://127.0.0.1:8000";

  const response = await fetch(`${apiUrl}/api/clubs`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Backend zwrócił status ${response.status}`);
  }

  return response.json();
}

export default async function ClubsPage() {
  let clubs: Club[] = [];
  let error: string | null = null;

  try {
    clubs = await getClubs();
  } catch (err) {
    console.error("Błąd pobierania klubów:", err);

    error =
      "Nie udało się pobrać klubów. Sprawdź, czy backend FastAPI jest uruchomiony na porcie 8000.";
  }

  return (
    <main className="min-h-screen bg-[#090d12] p-6 text-slate-100 lg:p-10">
      <div className="mx-auto max-w-7xl space-y-8">
        <header className="border-b border-white/10 pb-6">
          <p className="text-sm text-slate-500">
            Football Social Intelligence / Panel / Kluby
          </p>

          <h1 className="mt-3 text-3xl font-semibold">
            Football Clubs
          </h1>

          <p className="mt-2 text-slate-400">
            Zarządzanie monitorowanymi profilami polskich klubów
            piłkarskich.
          </p>
        </header>

        {error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-5 text-sm text-red-300">
            {error}
          </div>
        ) : (
          <ClubTable clubs={clubs} />
        )}
      </div>
    </main>
  );
}
