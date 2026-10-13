tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            sans: ['DM Sans', 'sans-serif'],
            serif: ['DM Serif Display', 'serif'],
          },
          colors: {
            primary: {
              50:  '#eef2ff',
              100: '#e0e7ff',
              200: '#c7d2fe',
              300: '#a5b4fc',
              400: '#818cf8',
              500: '#6366f1',
              600: '#4f46e5',
              700: '#4338ca',
              800: '#3730a3',
              900: '#312e81',
            },
          },
          animation: {
            'float': 'float 6s ease-in-out infinite',
            'float-delay': 'float 6s ease-in-out 2s infinite',
            'fade-up': 'fadeUp 0.6s ease both',
          },
          keyframes: {
            float: {
              '0%, 100%': { transform: 'translateY(0px)' },
              '50%': { transform: 'translateY(-12px)' },
            },
            fadeUp: {
              from: { opacity: '0', transform: 'translateY(24px)' },
              to:   { opacity: '1', transform: 'translateY(0)' },
            }
          }
        }
      }
    }
