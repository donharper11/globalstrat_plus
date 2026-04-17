import React from 'react';
import { ResponsiveContainer } from 'recharts';
import PanelCard from './PanelCard';

function ChartContainer({ title, headerColor = 'neutral', height = 250, children, actions }) {
  return (
    <PanelCard title={title} headerColor={headerColor} actions={actions}>
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </PanelCard>
  );
}

export default ChartContainer;
