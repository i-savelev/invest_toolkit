import pandas as pd
import matplotlib.pyplot as plt
from invest_toolkit import log


def _add_figure_watermark(
        fig, 
        text='@ваш_канал', 
        position='bottom-right', 
        fontsize=7, 
        color='gray', 
        alpha=0.8
        ):
    pos_map = {
        'bottom-right': (0.98, 0.02, 'right', 'bottom'),
        'bottom-left':  (0.02, 0.02, 'left',  'bottom'),
        'top-right':    (0.95, 0.95, 'right', 'top'),
        'top-left':     (0.02, 0.98, 'left',  'top'),
    }
    if position not in pos_map:
        raise ValueError(f"Недопустимая позиция: {position}. Варианты: {list(pos_map.keys())}")
    x, y, ha, va = pos_map[position]
    fig.text(
        x, y,
        text,
        transform=fig.transFigure,
        fontsize=fontsize,
        ha=ha,
        va=va,
        color=color,
        alpha=alpha
    )

def plot_one_chart(
    df:pd.DataFrame, 
    ticker:str,
    title:str, 
    window=3, 
    axes=None, 
    show:bool=True
    ):
    log.info(f'Построение графика {ticker}: {title}...')
    _df:pd.DataFrame = df[
            (df['ticker']==ticker) & 
            (df['indicator']==title)
        ].copy().set_index('year')
    
    if not _df.empty:
        row:pd.Series = _df['value']
        # row =  row.dropna()
        ax = row.plot(
            kind='bar',
            ax=axes,
            color="#182645",
            alpha=0.8,
            width=0.8,
            fontsize=12,
            label=title
            )
        ax.set_xlabel('')
        # --- Скользящая средняя ТОЛЬКО по годам ---
        if len(row.dropna()) >= window:
            rolling = row.rolling(window=window, min_periods=1).mean()
            # Наносим линию только на позиции годов
            year_positions = [i for i, label in enumerate(row.index)]
            ax.plot(
                year_positions,
                rolling,
                color="#D96060",
                linewidth=1,
                marker='o',
                markersize=3,
                label=f'Скольз. ср. ({window})'
            )
            ax.legend(fontsize=7)

        # --- Подписи значений ---
        for container in ax.containers:
            labels = []
            for v in container.datavalues:
                if v <10: labels.append(f'{v:.1f}' if pd.notna(v) else '')
                else: labels.append(f'{v:.0f}' if pd.notna(v) else '')

            ax.bar_label(
                container,
                labels,
                padding=2,
                fontsize=7
                )

        # --- Настройка оси Y с отступами ---
        valid_vals = row.dropna()
        if len(valid_vals) > 0:
            y_min = valid_vals.min()
            y_max = valid_vals.max()
            y_range = y_max - y_min if y_max != y_min else max(abs(y_max), 1)
            margin = y_range * 0.2
            ax.set_ylim(
                y_min - (margin if y_min >= 0 else margin * 1.5),
                y_max + margin
            )
        else:
            ax.set_ylim(0, 1)

        ax.set_title(title, fontsize=10)
        ax.grid(False)
        ax.tick_params(axis='x', labelsize=7, rotation=45)
        ax.tick_params(axis='y', labelsize=7)
        if show: plt.show()
        return ax
    else:
        log.warning(f'{ticker} или {title} нет в датафрейме!')
        return None


def plot_multiple_chart(
        df:pd.DataFrame,
        ticker:str,
        title:str,
        metric_list:list[str], 
        window:int=3, 
        rows:int=3, 
        cols:int= 2, 
        figsize = (12, 9.5)
        ):
    log.info(f'Построение графиков для {ticker}: {title}...')
    log.data(data = metric_list, label='Список показалей')
    main_title = title
    fig, axes = plt.subplots(nrows=rows, ncols=cols, figsize=figsize)
    fig.suptitle(main_title, fontsize=25, fontweight='black', y = 0.95)
    axes = axes.flatten()
    plot_idx = 0

    for param in df['indicator'].unique().tolist():
        if param not in metric_list:
            continue
        if plot_idx >= len(axes):
            log.warning(f'Количество показателей больше количества графиков [{len(axes)}]')
            break

        plot_one_chart(
            df,
            ticker=ticker,
            title=param,
            window=window,
            axes=axes[plot_idx],
            show=False
            )
        plot_idx += 1

    for j in range(plot_idx, len(axes)):
        axes[j].set_visible(False)
    plt.tight_layout(rect=(0, 0, 1, 0.95))
    _add_figure_watermark(
        fig=fig,
        text='@one_investor_fund',
        position='top-right',
        fontsize=14,
        color='gray'
    )
    plt.show()

