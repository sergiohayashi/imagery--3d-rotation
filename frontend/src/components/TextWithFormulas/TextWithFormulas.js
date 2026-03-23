import React from 'react';
import { InlineMath, BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';
import styles from "./TextWithFormulas.module.css"
// import CodeWithHighlighting from "../CodeWithHighlighting/CodeWithHighlighting";


const TextWithFormulas = ({ text }) => {
    // console.log( 'TEXT', text);
    // Function to split the text into text and formula parts
    const renderTextWithFormulas = (text) => {
        // Regex to find LaTeX formulas within the text
        const regex = /\\\[([\s\S]+?)\\\]|\\\((.+?)\\\)/g;
        let result = [];
        let lastIndex = 0;

        // Find all LaTeX formulas in the text
        text.replace(regex, (match, blockFormula, inlineFormula, index) => {
            // Add the text before the formula (if any)
            if (index > lastIndex) {
                // result.push(<span key={`f-text-${lastIndex}`}>{text.slice(lastIndex, index)}</span>);
                result.push(<>{text.slice(lastIndex, index)}</>);
            }

            // TODO: Quebra layout de tela quando habilitado text highlight
            // const textSegment = text.slice(lastIndex, index);
            // if (textSegment) {
            //     // Process the text segment for code highlighting
            //     result.push(<CodeWithHighlighting key={`text-${lastIndex}`} text={textSegment} />);
            // }

            // Determine if it's a block or inline formula
            const isBlock = blockFormula !== undefined;
            const formula = isBlock ? blockFormula : inlineFormula;
            const FormulaComponent = isBlock ? BlockMath : InlineMath;
            // Add the formula
            result.push(<FormulaComponent key={`formula-${index}`}>{formula}</FormulaComponent>);
            lastIndex = index + match.length;
        });

        // Add any remaining text after the last formula
        if (lastIndex < text.length) {
            // result.push(<span key={`f-text-${lastIndex}`}>{text.slice(lastIndex)}</span>);
            result.push(<>{text.slice(lastIndex)}</>);

            // TODO: Quebra layout de tela quando habilitado text highlight
            // const remainingText = text.slice(lastIndex);
            // result.push(<CodeWithHighlighting key={`text-${lastIndex}`} text={remainingText} />);
        }

        return result;
    };

    return <span>{renderTextWithFormulas(text)}</span>;
};

export default TextWithFormulas;
