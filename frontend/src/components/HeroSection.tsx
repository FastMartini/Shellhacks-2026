import { MomentumScene } from "./MomentumScene";

type HeroSectionProps = {
  onLaunchDashboard: () => void;
  onExploreScanner: () => void;
};

export function HeroSection({ onLaunchDashboard, onExploreScanner }: HeroSectionProps) {
  return (
    <section className="landing-hero" aria-labelledby="landing-title">
      <div className="hero-scene-background">
        <MomentumScene />
      </div>
      <div className="hero-copy">
        <p className="hero-eyebrow">Tokenized markets. Real momentum.</p>
        <h1 id="landing-title">Catch the move before the market <span className="hero-accent">slows down.</span></h1>
        <p className="lede">Discover momentum signals and trade tokenized US stocks on Solana—with a transparent record of every decision.</p>
        <div className="hero-actions">
          <button type="button" className="hero-primary" onClick={onLaunchDashboard}>Launch dashboard <span aria-hidden="true">↗</span></button>
          <button type="button" className="hero-secondary" onClick={onExploreScanner}>Explore scanner <span aria-hidden="true">→</span></button>
        </div>
      </div>
    </section>
  );
}
