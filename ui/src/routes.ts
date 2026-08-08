/**
 * Service-neutral browser history adapter. Service packages own their route grammar while this
 * hook owns pushState/popstate synchronization.
 * History API reference: https://developer.mozilla.org/en-US/docs/Web/API/History_API
 */
import {useCallback, useEffect, useState} from "react";

export function useBrowserRoute<T>(
  basePath: string,
  parse: (segments: string[]) => T,
  format: (route: T) => string,
): {route: T; navigate: (route: T, replace?: boolean) => void} {
  const read = useCallback(() => parse(pathSegments(window.location.pathname, basePath)), [basePath, parse]);
  const [route, setRoute] = useState<T>(read);

  useEffect(() => {
    const update = () => setRoute(read());
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, [read]);

  const navigate = useCallback((next: T, replace = false) => {
    const path = `${basePath.replace(/\/$/, "")}${format(next)}`;
    if (path !== window.location.pathname) {
      window.history[replace ? "replaceState" : "pushState"]({}, "", path);
    }
    setRoute(next);
  }, [basePath, format]);

  return {route, navigate};
}

export function encodePathSegment(value: string): string {
  return encodeURIComponent(value);
}

function pathSegments(pathname: string, basePath: string): string[] {
  const base = basePath.replace(/\/$/, "");
  if (pathname !== base && !pathname.startsWith(`${base}/`)) return [];
  const raw = pathname.slice(base.length).split("/").filter(Boolean);
  try {
    return raw.map(decodeURIComponent);
  } catch {
    return [];
  }
}
