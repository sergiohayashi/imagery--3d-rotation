import React from "react";
import styles from "./BreathingLoader.module.css"
import { FiFeather } from "react-icons/fi";

// const styles = {
//     container: {
//         minHeight: "100vh",
//         minWidth: "100vw",
//         display: "flex",
//         justifyContent: "center",
//         alignItems: "center",
//         background: "linear-gradient(135deg, #e0eafc 0%, #cfdef3 100%)",
//         flexDirection: "column"
//     }
// };

const BreathingLoader = () => {
    return (
        <div className={styles['container']}>
            <div className="breath-orb">
                <FiFeather size={64} color="#657786" />
            </div>
            <style>{`
        .breath-orb {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 140px;
          height: 140px;
          border-radius: 50%;
          background: radial-gradient(circle at 60% 40%, #232946 0%, #34315c 100%);
          box-shadow: 0 0 36px 8px #12cad6bb, 0 0 32px 2px #5636d799;
          animation: breathing 4s ease-in-out infinite;
        }
        @keyframes breathing {
          0% {
            transform: scale(1);
            box-shadow: 0 0 36px 8px #12cad6bb, 0 0 32px 2px #5636d799;
            opacity: 0.85;
          }
          30% {
            transform: scale(1.18);
            box-shadow: 0 0 70px 24px #12cad699, 0 0 54px 16px #5636d755;
            opacity: 1;
          }
          70% {
            transform: scale(1.18);
            box-shadow: 0 0 70px 24px #12cad699, 0 0 54px 16px #5636d755;
            opacity: 1;
          }
          100% {
            transform: scale(1);
            box-shadow: 0 0 36px 8px #12cad6bb, 0 0 32px 2px #5636d799;
            opacity: 0.85;
          }
        }
      `}</style>
        </div>
    );
};


export default BreathingLoader;
