import { useState, useEffect } from 'react';

// Floating particle component
function FloatingParticles() {
  const [particles] = useState(() =>
    Array.from({ length: 50 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      duration: Math.random() * 15 + 8,
      delay: Math.random() * 5,
    }))
  );

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((particle) => (
        <div
          key={particle.id}
          className="absolute rounded-full"
          style={{
            left: `${particle.x}%`,
            top: `${particle.y}%`,
            width: `${particle.size}px`,
            height: `${particle.size}px`,
            backgroundColor: particle.id % 3 === 0 ? '#22c55e' : particle.id % 3 === 1 ? '#06b6d4' : '#a855f7',
            opacity: 0.2,
            animation: `float-particle ${particle.duration}s ease-in-out infinite`,
            animationDelay: `${particle.delay}s`,
          }}
        />
      ))}
    </div>
  );
}

// Animated gradient orbs - faster movement
function GlowOrbs() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Green orb */}
      <div
        className="absolute w-96 h-96 rounded-full blur-3xl opacity-20"
        style={{
          background: 'radial-gradient(circle, #22c55e 0%, transparent 70%)',
          animation: 'orbit-1 12s ease-in-out infinite',
          top: '-10%',
          left: '-10%',
        }}
      />
      {/* Cyan orb */}
      <div
        className="absolute w-80 h-80 rounded-full blur-3xl opacity-15"
        style={{
          background: 'radial-gradient(circle, #06b6d4 0%, transparent 70%)',
          animation: 'orbit-2 15s ease-in-out infinite',
          bottom: '-5%',
          right: '-5%',
        }}
      />
      {/* Purple orb */}
      <div
        className="absolute w-64 h-64 rounded-full blur-3xl opacity-10"
        style={{
          background: 'radial-gradient(circle, #a855f7 0%, transparent 70%)',
          animation: 'orbit-3 10s ease-in-out infinite',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
        }}
      />
    </div>
  );
}

// Mouse-following glow hook
function useMouseGlow() {
  const [mousePos, setMousePos] = useState({ x: 50, y: 50 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({
        x: (e.clientX / window.innerWidth) * 100,
        y: (e.clientY / window.innerHeight) * 100,
      });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return mousePos;
}

// Animation CSS styles
const animationStyles = `
  @keyframes float-particle {
    0%, 100% {
      transform: translate(0, 0) scale(1);
      opacity: 0.2;
    }
    25% {
      transform: translate(10px, -20px) scale(1.2);
      opacity: 0.4;
    }
    50% {
      transform: translate(-5px, -40px) scale(1);
      opacity: 0.2;
    }
    75% {
      transform: translate(15px, -20px) scale(0.8);
      opacity: 0.3;
    }
  }

  @keyframes orbit-1 {
    0%, 100% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(30%, 20%);
    }
    50% {
      transform: translate(50%, 40%);
    }
    75% {
      transform: translate(20%, 30%);
    }
  }

  @keyframes orbit-2 {
    0%, 100% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(-20%, -30%);
    }
    50% {
      transform: translate(-40%, -20%);
    }
    75% {
      transform: translate(-30%, -40%);
    }
  }

  @keyframes orbit-3 {
    0%, 100% {
      transform: translate(-50%, -50%) scale(1);
    }
    33% {
      transform: translate(-30%, -70%) scale(1.2);
    }
    66% {
      transform: translate(-70%, -30%) scale(0.8);
    }
  }
`;

interface AnimatedBackgroundProps {
  children?: React.ReactNode;
  className?: string;
  showGrid?: boolean;
  showParticles?: boolean;
  showOrbs?: boolean;
  showMouseGlow?: boolean;
  fixed?: boolean;
}

export function AnimatedBackground({
  children,
  className = '',
  showGrid = true,
  showParticles = true,
  showOrbs = true,
  showMouseGlow = true,
  fixed = false,
}: AnimatedBackgroundProps) {
  const mousePos = useMouseGlow();

  // For fixed background mode (no children wrapper needed)
  if (fixed) {
    return (
      <>
        <div className={`fixed inset-0 overflow-hidden pointer-events-none ${className}`} style={{ zIndex: 0 }}>
          {showOrbs && <GlowOrbs />}
          {showParticles && <FloatingParticles />}
          {showGrid && <div className="absolute inset-0 bg-grid opacity-30" />}
          {showMouseGlow && (
            <div
              className="absolute w-96 h-96 rounded-full blur-3xl opacity-10 transition-all duration-700 ease-out"
              style={{
                background: 'radial-gradient(circle, #22c55e 0%, transparent 70%)',
                left: `${mousePos.x}%`,
                top: `${mousePos.y}%`,
                transform: 'translate(-50%, -50%)',
              }}
            />
          )}
        </div>
        {/* Animations CSS */}
        <style>{animationStyles}</style>
      </>
    );
  }

  return (
    <div className={`relative overflow-hidden ${className}`}>
      {/* Animated background elements */}
      {showOrbs && <GlowOrbs />}
      {showParticles && <FloatingParticles />}

      {/* Grid overlay */}
      {showGrid && <div className="absolute inset-0 bg-grid opacity-30 pointer-events-none" />}

      {/* Mouse-following glow */}
      {showMouseGlow && (
        <div
          className="absolute w-96 h-96 rounded-full blur-3xl opacity-10 pointer-events-none transition-all duration-700 ease-out"
          style={{
            background: 'radial-gradient(circle, #22c55e 0%, transparent 70%)',
            left: `${mousePos.x}%`,
            top: `${mousePos.y}%`,
            transform: 'translate(-50%, -50%)',
          }}
        />
      )}

      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>

      {/* CSS for animations */}
      <style>{animationStyles}</style>
    </div>
  );
}
