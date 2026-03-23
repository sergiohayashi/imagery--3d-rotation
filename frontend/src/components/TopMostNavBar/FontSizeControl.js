import React, { useState, useEffect } from 'react';

const FontSizeControl = () => {
    const [fontSize, setFontSize] = useState(16);

    useEffect(() => {
        document.documentElement.style.fontSize = `${fontSize}px`;
    }, [fontSize]);

    const handleChange = (event) => {
        setFontSize(Number(event.target.value));
    };

    return (
        <div style={{ marginBottom: '1rem' }}>
            <label htmlFor="fontSizeSlider">Font Size: {fontSize}px</label>
            <input
                id="fontSizeSlider"
                type="range"
                min="10"
                max="24"
                value={fontSize}
                onChange={handleChange}
                style={{ marginLeft: '0.5rem' }}
            />
        </div>
    );
};

export default FontSizeControl;
