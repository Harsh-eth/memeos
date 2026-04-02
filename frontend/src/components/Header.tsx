import { NavLink } from "react-router-dom";

const GITHUB_URL = import.meta.env.VITE_GITHUB_URL ?? "https://github.com";
const MEMEOS_BUY_URL = "https://jup.ag/tokens/FzoyNVEaSavbTHzidJgmBa3EQZ4AFvARhr3rPm9vBAGS";

const navClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? "ref-header__link ref-header__link--active" : "ref-header__link";

export function Header() {
  return (
    <header className="ref-header">
      <div className="ref-header__left">
        <span className="ref-header__mark" aria-hidden />
        <NavLink to="/" className="ref-header__logo-link" end>
          <span className="ref-header__logo">memeos</span>
        </NavLink>
      </div>
      <nav className="ref-header__nav" aria-label="Primary">
        <NavLink to="/workspace" className={navClass}>
          workspace
        </NavLink>
        <NavLink to="/feed" className={navClass}>
          feed
        </NavLink>
        <NavLink to="/history" className={navClass}>
          history
        </NavLink>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="ref-header__link"
        >
          github
        </a>
        <a
          href={MEMEOS_BUY_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="ref-buy__mono"
          aria-label="buy MEMEOS on Jupiter"
        >
          buy memEOS
        </a>
      </nav>
    </header>
  );
}
