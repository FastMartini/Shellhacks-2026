import { MomentumScene } from "./MomentumScene";

type HeroSectionProps = {
  onLaunchDashboard: () => void;
  onExploreScanner: () => void;
};

export function HeroSection({ onLaunchDashboard, onExploreScanner }: HeroSectionProps) {
  return (
    <section className="landing-hero">
      <div className="hero-scene-background">
        <MomentumScene />
      </div>
      <div className="hero-copy">
        <p className="eyebrow">Tokenized markets. Real momentum.</p>
        <h1>Catch the move before the market slows down.</h1>
        <p className="lede">Discover momentum signals and trade tokenized US stocks on Solana—with a transparent record of every decision.</p>
        <div className="hero-actions">
          <button className="hero-primary" onClick={onLaunchDashboard}>Launch dashboard <span aria-hidden="true">↗</span></button>
          <button className="hero-secondary" onClick={onExploreScanner}>Explore scanner <span aria-hidden="true">→</span></button>
        </div>
        <div className="hero-proof" aria-label="Platform highlights">
          <div><strong>24/7</strong><span>Solana settlement</span></div>
          <div><strong>Live</strong><span>Momentum signals</span></div>
          <div><strong>Clear</strong><span>Performance history</span></div>
        </div>
      </div>
    </section>
  );
}
