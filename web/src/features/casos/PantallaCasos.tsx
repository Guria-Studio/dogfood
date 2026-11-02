import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { ChevronDown, Search, TriangleAlert } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Avatar, BarraApilada, Prioridad } from "@/components/comun/Datos";
import { BadgeEstado, PestanasEstado } from "@/components/comun/Estado";
import { EncabezadoPagina } from "@/components/layout/EncabezadoPagina";
import { Vacio } from "@/components/layout/Vacio";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { type CasoFila, hace, useCasos } from "./api";
import { DetalleCaso } from "./DetalleCaso";
import { generarPlan } from "@/features/proyectos/api";

export interface BusquedaCasos {
  estado?: string;
  q?: string;
  prioridad?: string;
  caso?: string;
}

const texto = (v: unknown) => (typeof v === "string" && v ? v : undefined);

export const validarBusquedaCasos = (
  s: Record<string, unknown>,
): BusquedaCasos => ({
  estado: texto(s.estado),
  q: texto(s.q),
  prioridad: texto(s.prioridad),
  caso: texto(s.caso),
});

function Fila({ c, abrir }: { c: CasoFila; abrir: () => void }) {
  return (
    <li>
      <button
        type="button"
        data-caso={c.tc}
        onClick={abrir}
        className="flex w-full items-center gap-4 border-t px-4 py-3 text-left hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono">{c.tc}</span>
            <BadgeEstado estado={c.estado} />
            {c.fecha && <span>· {hace(c.fecha)}</span>}
          </div>
          <p className="mt-1 truncate font-medium">{c.nombre}</p>
          {c.falla && <p className="truncate text-sm text-danger">{c.falla}</p>}
        </div>
        <span className="hidden items-center gap-2 text-sm text-muted-foreground sm:flex">
          <Avatar nombre={c.persona.nombre} />
          <span className="max-w-32 truncate">{c.persona.nombre}</span>
        </span>
        <Prioridad nivel={c.prioridad} />
      </button>
    </li>
  );
}

function Grupo({
  nombre,
  casos,
  abrir,
}: {
  nombre: string;
  casos: CasoFila[];
  abrir: (tc: string) => void;
}) {
  const [abierto, setAbierto] = useState(true);
  const n = (e: string) => casos.filter((c) => c.estado === e).length;
  return (
    <section
      data-grupo={nombre}
      className="overflow-hidden rounded-lg border bg-card"
    >
      <button
        type="button"
        aria-expanded={abierto}
        onClick={() => setAbierto(!abierto)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm font-medium hover:bg-muted/50"
      >
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "size-4 transition-transform",
            !abierto && "-rotate-90",
          )}
        />
        {nombre}
        <span className="rounded bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">
          {casos.length}
        </span>
        <BarraApilada
          className="ml-auto"
          segmentos={[
            { valor: n("paso"), etiqueta: "Pasaron", clase: "bg-success" },
            {
              valor: n("fallo") + n("bloqueado") + n("no_concluyente"),
              etiqueta: "Fallaron",
              clase: "bg-danger",
            },
          ]}
        />
      </button>
      {abierto && (
        <ul>
          {casos.map((c) => (
            <Fila key={c.tc} c={c} abrir={() => abrir(c.tc)} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** Casos de prueba del proyecto agrupados por caso de uso; el detalle se abre en un sheet (`?caso=`). */
export function PantallaCasos() {
  const { proyecto } = useParams({ strict: false }) as { proyecto: string };
  const busqueda = useSearch({ strict: false }) as BusquedaCasos;
  const navigate = useNavigate();
  const lista = useCasos(proyecto, busqueda);
  const plan = useMutation({ mutationFn: () => generarPlan(proyecto) });
  const cambiar = (s: Partial<BusquedaCasos>) =>
    navigate({
      to: ".",
      search: ((previa: BusquedaCasos) => ({ ...previa, ...s })) as never,
      replace: "q" in s,
    });

  return (
    <>
      <EncabezadoPagina
        titulo="Casos de prueba"
        subtitulo="Todos los casos de este proyecto, agrupados por caso de uso, con su último resultado."
        ayuda="corrida"
        acciones={
          <label className="relative">
            <Search
              aria-hidden="true"
              className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              type="search"
              aria-label="Buscar casos"
              placeholder="Buscar por ID, nombre o persona"
              defaultValue={busqueda.q ?? ""}
              onChange={(e) => cambiar({ q: e.target.value || undefined })}
              className="w-64 pl-8"
            />
          </label>
        }
      />
      {lista.isPending ? (
        <Skeleton data-testid="cargando-casos" className="h-40 w-full" />
      ) : lista.isError ? (
        <Vacio
          icono={TriangleAlert}
          titulo="No se pudieron cargar los casos"
          texto="Revisa que el proyecto exista."
        />
      ) : (
        <>
          <PestanasEstado conteos={lista.data.conteos} />
          <div className="mt-4 space-y-3">
            {lista.data.grupos.length === 0 ? (
              lista.data.total ? (
                <Vacio
                  ilustracion="lista"
                  titulo="Ningún caso con esos filtros"
                />
              ) : (
                <Vacio
                  ilustracion="lista"
                  titulo="Genera el plan"
                  texto={
                    plan.error
                      ? plan.error.message
                      : plan.isSuccess
                        ? "Plan en marcha: vuelve en un momento."
                        : "Todavía no hay casos de prueba: dogfood plan los arma."
                  }
                  accion={
                    <Button
                      disabled={plan.isPending || !proyecto}
                      onClick={() => plan.mutate()}
                    >
                      Generar plan
                    </Button>
                  }
                />
              )
            ) : (
              lista.data.grupos.map((g) => (
                <Grupo
                  key={g.caso_de_uso}
                  nombre={g.caso_de_uso}
                  casos={g.casos}
                  abrir={(tc) => cambiar({ caso: tc })}
                />
              ))
            )}
          </div>
        </>
      )}
      <Sheet
        open={!!busqueda.caso}
        onOpenChange={(abierto) => !abierto && cambiar({ caso: undefined })}
      >
        <SheetContent
          side="right"
          className="w-[min(72rem,95vw)] max-w-none overflow-y-auto p-0"
        >
          <SheetTitle className="sr-only">
            Detalle del caso {busqueda.caso}
          </SheetTitle>
          <SheetDescription className="sr-only">
            Plan, vista previa, código e historial del caso.
          </SheetDescription>
          {busqueda.caso && (
            <DetalleCaso proyecto={proyecto} tc={busqueda.caso} expandible />
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}
