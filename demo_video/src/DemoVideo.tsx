import React from 'react';
import { AbsoluteFill, Img, spring, useCurrentFrame, useVideoConfig, staticFile } from 'remotion';
import { TransitionSeries, linearTiming } from '@remotion/transitions';
import { fade } from '@remotion/transitions/fade';

const ScreenSlide = ({ imageSrc, title, subtitle }: { imageSrc: string, title: string, subtitle: string }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Subtle zoom in
  const scale = spring({
    frame,
    fps,
    config: { damping: 100, stiffness: 20 },
    durationInFrames: 150
  });
  const mappedScale = 1 + (scale / 25); // Gentle scale from 1 to 1.04

  // Text fade in
  const textOpacity = spring({
    frame: frame - 15, // Delay text fade in
    fps,
    config: { damping: 100 },
  });

  return (
    <AbsoluteFill style={{ backgroundColor: '#f1f5f9', overflow: 'hidden' }}>
      <Img 
        src={staticFile(imageSrc)} 
        style={{ 
          width: '100%', 
          height: '100%', 
          objectFit: 'contain',
          transform: `scale(${mappedScale})`
        }} 
      />
      
      {/* Lower third text overlay */}
      <AbsoluteFill style={{
        justifyContent: 'flex-end',
        padding: '60px',
        opacity: textOpacity
      }}>
        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          padding: '40px',
          borderRadius: '16px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
          borderLeft: '8px solid #3b82f6',
          maxWidth: '80%'
        }}>
          <h1 style={{ fontFamily: 'sans-serif', fontSize: '60px', color: '#1e293b', margin: '0 0 10px 0', fontWeight: 'bold' }}>{title}</h1>
          <p style={{ fontFamily: 'sans-serif', fontSize: '34px', color: '#64748b', margin: 0 }}>{subtitle}</p>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const DemoVideo = () => {
  const SLIDE_DURATION = 120; // 4 seconds at 30fps

  const screens = [
    { id: '1', title: 'Real-time Dashboard', subtitle: 'Track your daily and monthly profits at a glance.', src: '1.png' },
    { id: '2', title: 'Lightning Fast POS', subtitle: 'Process orders and checkout in seconds.', src: '2.png' },
    { id: '3', title: 'Smart Invoicing', subtitle: 'Apply discounts, taxes, and generate PDFs instantly.', src: '3.png' },
    { id: '4', title: 'Complete Inventory', subtitle: 'Manage stock across multiple warehouses effortlessly.', src: '4.png' },
  ];

  return (
    <TransitionSeries>
      {screens.map((screen, index) => (
        <React.Fragment key={screen.id}>
          <TransitionSeries.Sequence durationInFrames={SLIDE_DURATION}>
            <ScreenSlide imageSrc={screen.src} title={screen.title} subtitle={screen.subtitle} />
          </TransitionSeries.Sequence>
          {index < screens.length - 1 && (
            <TransitionSeries.Transition
              presentation={fade()}
              timing={linearTiming({ durationInFrames: 20 })}
            />
          )}
        </React.Fragment>
      ))}
    </TransitionSeries>
  );
};
