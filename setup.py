import setuptools

setuptools.setup(
    name='cv_pipeliner',
    version='0.6.1',
    include_package_data=True,
    packages=setuptools.find_packages(),
    install_requires=[
        'nbformat>=5.0.7',
        'filterpy>=1.4.5',
        'imutils>=0.5.3',
        'imageio>=2.8.0',
        'ipywidgets>=7.5.1',
        'opencv_python>=4.3.0.36',
        'opencv-contrib-python-headless>=4.2.0.34',
        'scikit_learn>=0.23.2',
        'scikit-image>=0.17.2',
        'yacs>=0.1.8',
        'streamlit>=0.72.0',
        'dacite>=1.5.1',
        'gcsfs>=0.7.1',
        'fsspec>=0.8.4',
        'pathy>=0.3.3',
        'traceback_with_variables==1.1.9',
        'dataframe_image>=0.1.1',
        'tqdm>=4.40.2',
        'tensorflow>=2.4.1',
        'tensorflow-gpu>=2.4.1',
        'dash>=1.19.0',
        'dash-bootstrap-components>=0.11.3',
    ],
    extras_require={
        "tracking": [
            'imageio-ffmpeg>=0.4.2',
            "dash_bootstrap_components >= 0.12.0",
            "dash_interactive_graphviz >=0.3.0",
        ]
    },
    python_requires='>=3.8'
)
