"use client";

export function SkipLink() {
  return <a className="skip-link" href="#main" onClick={(event) => {
    const visibleMain = Array.from(document.querySelectorAll("main")).find((main) => main.getClientRects().length > 0);
    if (!visibleMain) return;
    event.preventDefault();
    visibleMain.tabIndex = -1;
    visibleMain.focus({ preventScroll: true });
    visibleMain.scrollIntoView();
  }}>Skip to content</a>;
}
