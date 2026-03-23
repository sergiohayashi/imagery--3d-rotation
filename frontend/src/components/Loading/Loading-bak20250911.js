import styles from './Loading.module.css';

function Loading({msg}) {
    return (
        <div className={styles.container}>
            <img
                src="/android-chrome-512x512.png"
                alt="App Logo"
                className={`${styles["logo"]}`}
            />
        </div>

    )
    ;
}

export default Loading;
