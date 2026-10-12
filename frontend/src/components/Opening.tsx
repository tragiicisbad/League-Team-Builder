import { useEffect, useRef, useState } from "react";
import { cinematic } from "../content";

export function Opening({ onDone }: { onDone: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [leaving, setLeaving] = useState(false);

  const finish = () => {
    setLeaving(true);
    window.setTimeout(onDone, 700);
  };

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) onDone();
    const video = videoRef.current;
    if (!video) return;
    const missing = window.setTimeout(() => {
      if (video.readyState < 2) onDone();
    }, 2500);
    return () => window.clearTimeout(missing);
  }, [onDone]);

  return (
    <div className={`opening ${leaving ? "is-leaving" : ""}`} role="dialog" aria-label="PCL cinematic opening">
      <video
        ref={videoRef}
        className="opening-video"
        autoPlay
        muted
        playsInline
        poster={cinematic.poster}
        onEnded={finish}
        onError={onDone}
      >
        <source src={cinematic.src} type="video/mp4" />
      </video>
      <div className="opening-shade" />
      <div className="opening-copy">
        <span className="eyebrow">{cinematic.eyebrow}</span>
      </div>
      <button className="opening-skip" type="button" onClick={finish}>
        {cinematic.skipLabel}
      </button>
    </div>
  );
}
