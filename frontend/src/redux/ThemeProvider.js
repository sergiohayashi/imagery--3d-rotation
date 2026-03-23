import React, { useState, useEffect } from 'react';
import { ThemeContext } from './ThemeContext';
export function ThemeProvider({ children }) {
    const [theme, setTheme] = useState(() => {
        const savedTheme = localStorage.getItem('theme');
        return savedTheme || 'dark';
    });

    // Update local storage whenever the theme changes
    useEffect(() => {
        localStorage.setItem('theme', theme);
    }, [theme]);

    const switchTheme = () => {
        setTheme(prevTheme => prevTheme === 'dark' ? 'light' : 'dark');
    };

    return (
        <ThemeContext.Provider value={{ theme, switchTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}
