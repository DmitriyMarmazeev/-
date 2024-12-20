const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin'); 

module.exports = {
    entry: './src/index.js',  // Путь к вашему основному файлу
    output: {
      path: path.resolve(__dirname, 'dist'),
      filename: 'main.js',
    },
  
    mode: 'production',
  
    module: {
      rules: [
        {
          test: /\.js$/,
          use: 'babel-loader',
          exclude: /node_modules/
        },
        {
          test: /\.css$/,  // Обработка CSS
          use: [
            MiniCssExtractPlugin.loader,  // Выделение стилей в отдельный файл
            'css-loader',  // Для импорта CSS файлов
            'postcss-loader'  // Для обработки через PostCSS (если нужно)
          ]
        }
      ]
    },
  
    plugins: [
      new HtmlWebpackPlugin({
        template: './src/index.html',  // Ваш HTML-шаблон
      }),
      new CleanWebpackPlugin(),
      new MiniCssExtractPlugin({
        filename: 'styles.css',  // Выводимый файл стилей
      })
    ]
  };
  