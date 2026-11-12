
type Snapshot = {
  id: number;
  followers_count: number | null;
  likes_count: number | null;
  collected_at: string;
};

type FollowersResponse = {
  club_id: number;
  club_name: string;
  tiktok_handle: string;
  latest: Snapshot | null;
  growth_since_previous_snapshot: number | null;
  history: Snapshot[];
};

const numberFormat = new Intl.NumberFormat("pl-PL");

const dateFormat = new Intl.DateTimeFormat("pl-PL", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Europe/Warsaw",
});

async function getFollowers(
  clubId: number
): Promise<FollowersResponse | null> {
  const apiUrl =
    process.env.FSI_API_URL || "http://127.0.0.1:8000";

  try {
    const response = await fetch(
      `${apiUrl}/api/clubs/${clubId}/followers?limit=100`,
      { cache: "no-store" }
    );

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error("Błąd pobierania obserwujących:", error);
    return null;
  }
}

function FollowersChart({
  history,
}: {
  history: Snapshot[];
}) {
  const points = history.filter(
    (snapshot): snapshot is Snapshot & {
      followers_count: number;
    } =>
      snapshot.followers_count !== null &&
      Number.isFinite(snapshot.followers_count)
  );

  if (points.length < 2) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-slate-500">
        Potrzebujemy co najmniej dwóch pomiarów do wykresu.
      </div>
    );
  }

  const values = points.map((point) => point.followers_count);
  const min = Math.min(...values);
  const max = Math.max(...values);

  const range = max - min || 1;

  const width = 800;
  const height = 240;
  const padding = 30;

  const times = points.map((point) =>
    new Date(point.collected_at).getTime()
  );

  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const timeRange = maxTime - minTime || 1;

  const coords = points.map((point, index) => {
    const x =
      padding +
      ((times[index] - minTime) / timeRange) *
        (width - padding * 2);

    const y =
      height -
      padding -
      ((point.followers_count - min) / range) *
        (height - padding * 2);

    return { x, y };
  });

  const path = coords
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`
    )
    .join(" ");

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label="Wykres liczby obserwujących w czasie"
      >
        {[0, 1, 2, 3, 4].map((i) => {
          const y =
            padding + (i / 4) * (height - padding * 2);

          return (
            <line
              key={i}
              x1={padding}
              x2={width - padding}
              y1={y}
              y2={y}
              stroke="#334155"
              strokeDasharray="4 6"
            />
          );
        })}

        <path
          d={path}
          fill="none"
          stroke="#34d399"
          strokeWidth="3"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {coords.map((point, index) => (
          <circle
            key={points[index].id}
            cx={point.x}
            cy={point.y}
            r="4"
            fill="#34d399"
          >
            <title>
              {`${dateFormat.format(
                new Date(points[index].collected_at)
              )}: ${numberFormat.format(
                points[index].followers_count
              )}`}
            </title>
          </circle>
        ))}
      </svg>

      <div className="mt-2 flex justify-between text-xs text-slate-500">
        <span>
          {dateFormat.format(new Date(points[0].collected_at))}
        </span>
        <span>
          {dateFormat.format(
            new Date(points[points.length - 1].collected_at)
          )}
        </span>
      </div>
    </div>
  );
}

export default async function FollowersPanel({
  clubId,
}: {
  clubId: number;
}) {
  const data = await getFollowers(clubId);

  if (!data) {
    return (
      <section className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-red-300">
        Nie udało się pobrać statystyk obserwujących z API.
      </section>
    );
  }

  const latest = data.latest;
  const growth = data.growth_since_previous_snapshot;

  return (
    <section className="space-y-5">
      <h2 className="text-xl font-semibold">
        Analiza obserwujących
      </h2>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
          <p className="text-sm text-slate-400">
            Ostatni odczyt obserwujących
          </p>
          <p className="mt-4 text-3xl font-semibold text-emerald-400">
            {latest?.followers_count == null
              ? "—"
              : numberFormat.format(latest.followers_count)}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Przybliżona wartość, jeśli TikTok zaokrąglił licznik.
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
          <p className="text-sm text-slate-400">
            Zmiana od poprzedniego pomiaru
          </p>
          <p className="mt-4 text-3xl font-semibold">
            {growth == null
              ? "—"
              : `${growth > 0 ? "+" : ""}${numberFormat.format(growth)}`}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Różnica dwóch odczytów, niekoniecznie dzienna.
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
          <p className="text-sm text-slate-400">
            Ostatnia aktualizacja
          </p>
          <p className="mt-4 text-lg font-semibold">
            {latest
              ? dateFormat.format(new Date(latest.collected_at))
              : "Brak danych"}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Czas polski
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
        <h3 className="mb-2 text-lg font-semibold">
          Historia obserwujących
        </h3>
        <p className="mb-6 text-sm text-slate-400">
          Ostatnie {data.history.length} zapisanych pomiarów
        </p>

        <FollowersChart history={data.history} />
      </div>
    </section>
  );
}
