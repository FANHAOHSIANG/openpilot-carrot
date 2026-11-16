package tw.carrot.led;
import java.nio.file.*;
public final class VehicleRulesTests {
 public static void main(String[] args) throws Exception {
  VehicleRules rules=new VehicleRules();String previous="";int checks=0;
  for(String row:Files.readAllLines(Path.of("tests/vehicle_scenarios.csv"))){
   String[] c=row.split(",",-1);if(c[0].equals("scenario"))continue;
   if(!previous.equals(c[0])){rules.reset();previous=c[0];}
   String result=rules.choose(Double.parseDouble(c[2]),Double.parseDouble(c[3]),c[4].equals("1"),c[5].equals("1"),c[6].equals("1"),c[7],Long.parseLong(c[1]));
   if(!result.equals(c[8]) || rules.emergencyActive!=c[9].equals("1"))throw new AssertionError(c[0]+" @"+c[1]+": expected "+c[8]+"/"+c[9]+" got "+result+"/"+rules.emergencyActive);
   checks++;
  }
  System.out.println(checks+" shared emergency/regen/gear/stale replay samples passed");
 }
}
