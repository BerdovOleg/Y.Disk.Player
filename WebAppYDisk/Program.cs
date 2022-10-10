using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using YandexDisk.Client.Clients;
using YandexDisk.Client.Http;
using YandexDisk.Client.Protocol;

namespace WebAppYDisk
{
    class MainClass
    {
        public static void Main(string[] args)
        {
            var  path = ("/Users/olegberdov/Projects/WebAppYDisk/WebAppYDisk/token.txt");
            string token = "";
            try
            {
                var a = File.ReadLines(path);
                foreach (var item in a)
                {
                    Console.Write(item);
                    token += item;
                }
            }
            catch (Exception ex)
            { Console.WriteLine(ex.Message); }
            write("\n");
            write(token);
    
            //diskHttpApi(token);
            if ()
            {
                Task.Run(async () =>

               {
                   try
                   {
                       var api = new DiskHttpApi(token);
                       var rootFolderData = await api.MetaInfo.GetInfoAsync(new ResourceRequest
                       {
                           Path = "/"
                       });

                       foreach (var item in rootFolderData.Embedded.Items)
                       {
                           write($"{item.Name}\t{item.Type}\t{item.MimeType}");
                       }
                   //директория
                   const string folderName = "test_folder";

                   //создание директории
                   if (!rootFolderData.Embedded.Items.Any(i => i.Type == ResourceType.Dir &
                        i.Name.Equals(folderName)))
                       {
                           await api.Commands.CreateDictionaryAsync("/" + folderName);
                       }

                   //определение файлов для загрузки
                   string sourceDirectory = @"/Users/olegberdov/Projects/WebAppYDisk";
                       var files = Directory.GetFiles(sourceDirectory, "*.txt");
                   // загрузка файлов на диск 
                   foreach (var file in files)
                       {
                           try
                           {
                               var link = await api.Files.GetUploadLinkAsync("/" +
                                   folderName + "/" + Path.GetFileName(file), overwrite: false);

                               using (var fs = File.OpenRead(file))
                               {
                                   await api.Files.UploadAsync(link, fs);
                               }
                           }
                           catch (Exception ex)
                           { Console.WriteLine(ex.Message); }
                       }

                       var testFolderData = await api.MetaInfo.GetInfoAsync(new ResourceRequest
                       {
                           Path = "/" + folderName
                       });

                   //вывод на содержимое содержимое директории на Я.диске
                   foreach (var item in testFolderData.Embedded.Items)
                       {
                           write($"{item.Name}\t{item.Type}\t{item.MimeType}");
                       }

                   //создание директории
                   var destDir = Path.Combine(Environment.CurrentDirectory, "Download");
                       if (!Directory.Exists(destDir))
                       {
                           Directory.CreateDirectory(destDir);
                       }

                   //загрузка файлов
                   foreach (var item in testFolderData.Embedded.Items)
                       {
                           await api.Files.DownloadFileAsync(path: item.Path, Path.Combine(destDir, item.Name));
                           var link = await api.Files.GetDownloadLinkAsync(item.Path);

                           write(item.Name + "\t" + link.Href);
                       }

                   }
                   catch (Exception ex)
                   {
                       Console.WriteLine(ex.Message);
                   }
               });
            }

            Console.WriteLine("Hello World!");
            Console.ReadKey();


             void write(string s)
            {
                Console.WriteLine(s);
            }
        }
       
    }
}
